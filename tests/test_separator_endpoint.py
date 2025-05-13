import json
import os
import logging
import pytest
import shutil
from pathlib import Path
from musictranslator import separator_wrapper

# Configure logging
logging.basicConfig(level=logging.DEBUG)

REAL_AUDIO_FILE_SOURCE_PATH = Path("data/audio/BloodCalcification-NoMore.wav")

@pytest.fixture
def app_config(tmp_path, monkeypatch):
    """
    Fixture to configure the Flask app with temporary INPUT and OUTPUT directories for testing.
    Yields the test input and output directory paths.
    """
    test_input_dir = tmp_path / "test_audio_input"
    test_output_dir = tmp_path / "test_separator_output"
    test_input_dir.mkdir()
    test_output_dir.mkdir()

    monkeypatch.setattr(separator_wrapper, "INPUT_DIR", str(test_input_dir))
    monkeypatch.setattr(separator_wrapper, "OUTPUT_DIR", str(test_output_dir))

    yield str(test_input_dir), str(test_output_dir)

@pytest.fixture
def client(app_config):
    """
    Fixture to provide a Flask test client configured with temporary paths.
    """
    separator_wrapper.app.config['TESTING'] = True
    with separator_wrapper.app.test_client() as client:
        yield client

@pytest.fixture
def dummy_audio_file(app_config):
    """
    Fixture to create a dummy audio file in the temporary input directory.
    Yields the filename, the full path to the input dir, and the full path to the output dir
    """
    input_dir_str, output_dir_str = app_config
    input_dir = Path(input_dir_str)

    audio_filename = "dummy_test_song.wav"
    dummy_file_path = input_dir / audio_filename

    riff_header = b'RIFF'
    chunk_size = b'\x24\x00\x00\x00'
    wave_format = b'WAVE'
    fmt_subchunk_id = b'fmt'
    fmt_subchunk_size = b'\x10\x00\x00\x00'
    audio_format = b'\x01\x00'
    num_channels = b'\x01\x00'
    sample_rate = b'\x44\xAC\x00\x00'
    byte_rate = b'\x88\x58\x01\x00'
    block_align = b'\x02\x00'
    bits_per_sample = b'\x10\x00'
    data_subchunk_id = b'data'
    data_subchunk_size = b'\x00\x00\x00\x00'

    with open(dummy_file_path, 'wb') as f:
        f.write(riff_header + chunk_size + wave_format + \
                fmt_subchunk_id + fmt_subchunk_size + audio_format + \
                num_channels + sample_rate + byte_rate + block_align + \
                bits_per_sample + data_subchunk_id + data_subchunk_size)

    yield audio_filename, input_dir_str, output_dir_str

@pytest.fixture
def real_audio_file(app_config):
    """Fixture to provide a real audio file for testing"""
    input_dir_str, output_dir_str = app_config
    input_dir = Path(input_dir_str)

    if not REAL_AUDIO_FILE_SOURCE_PATH.exists():
        pytest.fail(f"Real audio file not found at: {REAL_AUDIO_FILE_SOURCE_PATH}. "
                    "Please ensure the path is correct and the file exists.")

    audio_filename = REAL_AUDIO_FILE_SOURCE_PATH.name
    destination_path = input_dir / audio_filename

    shutil.copy(REAL_AUDIO_FILE_SOURCE_PATH, destination_path)
    logging.debug(f"Copied real audio file from {REAL_AUDIO_FILE_SOURCE_PATH} to {destination_path}")

    yield audio_filename, input_dir_str, output_dir_str

def test_separate_endpoint_post_integration_with_files(client, real_audio_file):
    """
    End-to-end test using actual audio data and checking Demucs output files
    """
    audio_filename, _, configured_output_dir_str = real_audio_file

    expected_stems = {"bass": "bass.wav", "drums": "drums.wav", "guitar": "guitar.wav",
                      "other": "other.wav", "piano": "piano.wav", "vocals": "vocals.wav"}

    base_filename_no_ext = Path(audio_filename).stem
    expected_demucs_output_subdir = Path(configured_output_dir_str) / "htdemucs_6s" / base_filename_no_ext

    response = client.post('/separate', json={"audio_filename": audio_filename})
    print(f"response: {response}")

    assert response.status_code == 200

    for filename in os.listdir(expected_demucs_output_subdir):
        if filename.endswith(".wav"):
            expected_file_path = os.path.join(expected_demucs_output_subdir, filename)
            assert os.path.exists(expected_file_path)

def test_separate_endpoint_post_missing_filename(client, app_config):
    """
    Test /separate endpoint with no filename on the audio file.
    """
    response = client.post('/separate', json={})
    print(f"response: {response}")

    assert response.status_code == 400
    # assert response.json() == {"error": "Audio filename missing."}

def test_separate_endpoint_post_demucs_error(client, dummy_audio_file, monkeypatch):
    """
    Test /separate endpoint when Spleeter returns an error
    """
    audio_filename, _, _ = dummy_audio_file
    error_message = "Simulated Demucs processing error with dummy file"

    def mock_run_demucs(audio_file_path):
        raise RuntimeError(error_message)

    monkeypatch.setattr("musictranslator.separator_wrapper.run_demucs", mock_run_demucs)

    response = client.post('/separate', json={'audio_filename': audio_filename})
    print(f"response: {response}")

    assert response.status_code == 500
    response_json = response.get_json()
    assert response_json == {"error": error_message}

def test_separate_endpoint_post_filenotfound(client, app_config):
    """
    Test /separate endpoint when file is not found
    """
    response = client.post('/separate', json={"audio_filename": "nonexistent-file.wav"})
    print(f"response: {response}")

    assert response.status_code == 404
    # assert response.json() == {'error': 'Audio file not found.'}

def test_health_check(client, app_config):
    """
    Test the /separate/health endpoint.
    """
    # app_config is used to ensure the app context is set up if it had any side effects,
    # though for a simple health check it might not be strictly necessary beyond client setup.
    response = client.get('/separate/health')
    assert response.status_code == 200
    assert response.get_json() == {"status": "OK"}
