import os
import uuid
import shutil
import tempfile
import mimetypes
import zipfile
from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from PIL import Image

# Real-ESRGAN imports
from realesrgan import RealESRGANer
from basicsr.archs.rrdbnet_arch import RRDBNet

app = Flask(__name__, static_folder='static', static_url_path='')

UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'image_upscaler_uploads')
RESULT_FOLDER = os.path.join(tempfile.gettempdir(), 'image_upscaler_results')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff', 'tif'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB per file

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Cache loaded models
_models_cache = {}


def get_device():
    """Auto-detect best available device."""
    import torch
    if torch.cuda.is_available():
        return 'cuda'
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'


def get_upsampler(model_name='RealESRGAN_x4plus', scale=4):
    """Get or create a cached Real-ESRGAN upsampler."""
    cache_key = model_name
    if cache_key in _models_cache:
        upsampler = _models_cache[cache_key]
        upsampler.outscale = scale
        return upsampler

    device = get_device()
    half = device != 'cpu'

    if model_name == 'RealESRGAN_x4plus':
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=23, num_grow_ch=32, scale=4
        )
        netscale = 4
        model_url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'
    elif model_name == 'RealESRGAN_x4plus_anime_6B':
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=6, num_grow_ch=32, scale=4
        )
        netscale = 4
        model_url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth'
    else:
        raise ValueError(f'Unknown model: {model_name}')

    # Model weights will be auto-downloaded to weights/ folder
    model_path = os.path.join('weights', os.path.basename(model_url))

    upsampler = RealESRGANer(
        scale=netscale,
        model_path=model_path if os.path.exists(model_path) else model_url,
        dni_weight=None,
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=half,
        device=device,
    )
    upsampler.outscale = scale
    _models_cache[cache_key] = upsampler
    return upsampler


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/upscale', methods=['POST'])
def upscale_images():
    """Handle image upscale requests. Returns JSON with result file paths."""
    if 'images' not in request.files:
        return jsonify({'error': 'No images provided'}), 400

    files = request.files.getlist('images')
    if not files or len(files) == 0:
        return jsonify({'error': 'No images provided'}), 400

    if len(files) > 50:
        return jsonify({'error': 'Maximum 50 images allowed per batch'}), 400

    scale = int(request.form.get('scale', 4))
    if scale not in [2, 3, 4]:
        return jsonify({'error': 'Scale must be 2, 3, or 4'}), 400

    model_name = request.form.get('model', 'RealESRGAN_x4plus')
    if model_name not in ['RealESRGAN_x4plus', 'RealESRGAN_x4plus_anime_6B']:
        return jsonify({'error': 'Invalid model name'}), 400

    # Create a unique session folder for this request
    session_id = str(uuid.uuid4())
    session_upload = os.path.join(UPLOAD_FOLDER, session_id)
    session_result = os.path.join(RESULT_FOLDER, session_id)
    os.makedirs(session_upload, exist_ok=True)
    os.makedirs(session_result, exist_ok=True)

    try:
        upsampler = get_upsampler(model_name, scale)
        results = []

        for file in files:
            if file and allowed_file(file.filename):
                original_name = secure_filename(file.filename)
                if not original_name:
                    original_name = f'image_{uuid.uuid4().hex[:8]}.png'

                # Save uploaded file
                input_path = os.path.join(session_upload, original_name)
                file.save(input_path)

                # Read image with OpenCV
                img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue

                # Upscale
                try:
                    output, _ = upsampler.enhance(img, outscale=scale)
                except RuntimeError as e:
                    # If out of memory, try with tiling
                    if 'out of memory' in str(e).lower() or 'mps' in str(e).lower():
                        upsampler.tile = 256
                        output, _ = upsampler.enhance(img, outscale=scale)
                        upsampler.tile = 0
                    else:
                        raise

                # Determine output format - keep original extension
                name_base, ext = os.path.splitext(original_name)
                if ext.lower() in ['.jpg', '.jpeg']:
                    output_path = os.path.join(session_result, original_name)
                    cv2.imwrite(output_path, output, [cv2.IMWRITE_JPEG_QUALITY, 95])
                elif ext.lower() == '.webp':
                    output_path = os.path.join(session_result, original_name)
                    cv2.imwrite(output_path, output, [cv2.IMWRITE_WEBP_QUALITY, 95])
                else:
                    # Default to PNG for lossless
                    output_name = name_base + '.png'
                    output_path = os.path.join(session_result, output_name)
                    cv2.imwrite(output_path, output)

                # Get output dimensions
                h, w = output.shape[:2]
                output_basename = os.path.basename(output_path)
                results.append({
                    'original_name': original_name,
                    'output_name': output_basename,
                    'width': w,
                    'height': h,
                    'preview_url': f'/api/preview/{session_id}/{output_basename}',
                    'download_url': f'/api/download/{session_id}/{output_basename}'
                })

        # Cleanup upload folder
        shutil.rmtree(session_upload, ignore_errors=True)

        if not results:
            return jsonify({'error': 'No valid images were processed'}), 400

        return jsonify({
            'success': True,
            'session_id': session_id,
            'results': results,
            'scale': scale,
            'model': model_name
        })

    except Exception as e:
        # Cleanup on error
        shutil.rmtree(session_upload, ignore_errors=True)
        shutil.rmtree(session_result, ignore_errors=True)
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500


@app.route('/api/preview/<session_id>/<filename>')
def preview_file(session_id, filename):
    """Serve an upscaled image inline for preview."""
    safe_name = secure_filename(filename)
    result_dir = os.path.join(RESULT_FOLDER, secure_filename(session_id))
    file_path = os.path.join(result_dir, safe_name)

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    mimetype = mimetypes.guess_type(safe_name)[0] or 'application/octet-stream'
    return send_file(file_path, mimetype=mimetype)


@app.route('/api/download/<session_id>/<filename>')
def download_file(session_id, filename):
    """Download a single upscaled image as attachment."""
    safe_name = secure_filename(filename)
    result_dir = os.path.join(RESULT_FOLDER, secure_filename(session_id))
    file_path = os.path.join(result_dir, safe_name)

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    mimetype = mimetypes.guess_type(safe_name)[0] or 'application/octet-stream'
    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=safe_name
    )


@app.route('/api/download-zip/<session_id>')
def download_zip(session_id):
    """Download all upscaled images as a ZIP file."""
    result_dir = os.path.join(RESULT_FOLDER, secure_filename(session_id))

    if not os.path.exists(result_dir):
        return jsonify({'error': 'Session not found'}), 404

    # Create ZIP in memory
    zip_path = os.path.join(tempfile.gettempdir(), f'upscaled_{session_id}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(result_dir):
            fpath = os.path.join(result_dir, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, fname)

    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name='upscaled_images.zip'
    )


@app.route('/api/cleanup/<session_id>', methods=['POST'])
def cleanup_session(session_id):
    """Cleanup result files for a session."""
    result_dir = os.path.join(RESULT_FOLDER, secure_filename(session_id))
    shutil.rmtree(result_dir, ignore_errors=True)
    # Also cleanup zip if exists
    zip_path = os.path.join(tempfile.gettempdir(), f'upscaled_{session_id}.zip')
    if os.path.exists(zip_path):
        os.remove(zip_path)
    return jsonify({'success': True})


if __name__ == '__main__':
    print("🚀 Image Upscaler starting...")
    print(f"📱 Device: {get_device()}")
    print(f"🌐 Open http://localhost:8000 in your browser")
    app.run(host='0.0.0.0', port=8000, debug=True)
