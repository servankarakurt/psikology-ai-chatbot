class ChatResult {
  ChatResult({
    required this.reply,
    required this.sessionId,
    required this.isCrisis,
  });

  final String reply;
  final int? sessionId;
  final bool isCrisis;
}

class MobileChatResult {
  MobileChatResult({
    required this.reply,
    required this.transcript,
    required this.audioBase64,
    required this.sessionId,
    required this.ttsError,
  });

  final String reply;
  final String transcript;
  final String? audioBase64;
  final int? sessionId;
  final String? ttsError;
}
