"""REST API for the CD Audio Capture Service."""

from flask import Blueprint, jsonify, request

from server.services.capture import CaptureService


def create_capture_api(capture_service: CaptureService, playback_runtime=None) -> Blueprint:
    """Create the capture API blueprint.

    Args:
        capture_service: The capture service instance.
        playback_runtime: Optional PlaybackRuntime, required for the
            ``/record-current`` endpoint (records whatever is playing now).
    """
    bp = Blueprint("capture", __name__, url_prefix="/api/capture")

    @bp.route("/start", methods=["POST"])
    def start_capture():
        """Start a capture session."""
        data = request.get_json(silent=True) or {}
        deck = data.get("deck")
        release_id = data.get("release_id")
        limit = data.get("limit")
        result = capture_service.start(deck=deck, release_id=release_id, limit=limit)
        status_code = 200 if "error" not in result else 409
        return jsonify(result), status_code

    @bp.route("/stop", methods=["POST"])
    def stop_capture():
        """Stop the capture session."""
        result = capture_service.stop()
        status_code = 200 if "error" not in result else 409
        return jsonify(result), status_code

    @bp.route("/pause", methods=["POST"])
    def pause_capture():
        """Pause the capture session."""
        result = capture_service.pause()
        status_code = 200 if "error" not in result else 409
        return jsonify(result), status_code

    @bp.route("/resume", methods=["POST"])
    def resume_capture():
        """Resume from pause."""
        result = capture_service.resume()
        status_code = 200 if "error" not in result else 409
        return jsonify(result), status_code

    @bp.route("/status", methods=["GET"])
    def capture_status():
        """Full status snapshot."""
        return jsonify(capture_service.status()), 200

    @bp.route("/progress", methods=["GET"])
    def capture_progress():
        """Lightweight progress for polling."""
        return jsonify(capture_service.progress()), 200

    @bp.route("/current", methods=["GET"])
    def capture_current():
        """What is being captured right now."""
        return jsonify(capture_service.current()), 200

    @bp.route("/log", methods=["GET"])
    def capture_log():
        """Return recent log lines."""
        lines = request.args.get("lines", 50, type=int)
        return jsonify({"log": capture_service.log(lines)}), 200

    @bp.route("/record-current", methods=["POST"])
    def record_current():
        """Record the currently playing track. Auto-stops on track change."""
        if playback_runtime is None:
            return jsonify({"error": "Playback runtime not available"}), 503
        result = capture_service.record_current(playback_runtime)
        status_code = 200 if "error" not in result else 409
        return jsonify(result), status_code

    return bp
