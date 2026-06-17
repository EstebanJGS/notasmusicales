from flask import Flask, request, jsonify
import struct
from fourier import detect_pitch, freq_to_note

app = Flask(__name__)

last_note = {}   # dedupe por device_id


@app.route('/audio', methods=['POST'])
def audio():
    sample_rate = int(request.headers.get('X-Sample-Rate', 8000))
    raw = request.data

    if len(raw) < 2:
        return jsonify({"error": "body vacío"}), 400

    # uint16 little-endian enviado por el ESP32 (0-4095 del ADC de 12 bits)
    samples = struct.unpack(f'<{len(raw) // 2}H', raw)

    freq = detect_pitch(samples, sample_rate)
    note, cents = freq_to_note(freq)
    device_id = request.remote_addr

    if note and last_note.get(device_id) != note:
        last_note[device_id] = note
        # save_to_db(device_id, note, freq, cents)   <- solo aquí escribe BD
        print(f"{device_id}: {note} ({freq:.1f} Hz, {cents:+.0f}c)")

    return jsonify({"note": note, "freq": round(freq, 2), "cents": round(cents, 1)}), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
