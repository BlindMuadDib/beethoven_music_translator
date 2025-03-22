"""
A wrapper for the Spleeter by Deezer source separation library
"""
from flask import Flask, request, jsonify
from kubernetes import client, config, stream

app = Flask(__name__)

# Configure Kubernetes client
try:
    config.load_incluster_config() # For running inside a pod
except config.config_exception.ConfigException:
    config.load_kube_config() # For running locally

v1 = client.CoreV1Api()
batch_v1 = client.BatchV1Api()
apps_v1 = client.AppsV1Api()

def execute_command_in_pod(pod_name, namespace, command):
    """Execute a command in a Kubernetes pod"""
    try:
        exec_command = ["/bin/sh", "-c", command]
        resp = stream.stream(
            v1.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        return resp
    except client.exceptions.ApiException as e:
        return f"Error executing command: {e}"

def get_spleeter_pod_name(namespace):
    """Gets the name of the Spleeter pod"""
    try:
        pods = v1.list_namespaced_pod(namespace, label_selector="app=spleeter")
        if pods.items:
            return pods.items[0].metadata.name
        return None
    except client.exceptions.ApiException as e:
        return f"Error getting pod name: {e}"

@app.route('/split', methods=['POST'])
def split():
    """Splits an audio file into stems"""
    if 'audio' not in request.diles:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    input_file_path = "/input_output/input.wav"
    output_dir = "/input_output"
    namespace = "default"

    audio_file.save("/input_output/input.wav")

    pod_name = get_spleeter_pod_name(namespace)
    if not pod_name:
        return jsonify({"error": "Spleeter pod not found."}), 500
    if "Error" in pod_name:
        return jsonify({"error": pod_name}), 500

    command = (
        "spleeter separate -p spleeter:4stems-16kHz "
        f"-o {output_dir} -f {{instrument}}.wav "
        f"-i {input_file_path}"
    )
    result = execute_command_in_pod(pod_name, namespace, command)

    if "Error" in result:
        return jsonify({"error": result}), 500

    return jsonify({
        "bass": f"{output_dir}/bass.wav",
        "drums": f"{output_dir}/drums.wav",
        "other": f"{output_dir}/other.wav",
        "vocals": f"{output_dir}/vocals.wav",
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
