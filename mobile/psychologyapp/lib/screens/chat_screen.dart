import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:record/record.dart';

import '../models/auth_models.dart';
import '../services/api_service.dart';
import 'profile_screen.dart';

class ChatArgs {
  ChatArgs({
    required this.userId,
    required this.userName,
    required this.age,
    required this.gender,
    required this.profession,
    required this.city,
  });

  final int? userId;
  final String userName;
  final int age;
  final String gender;
  final String profession;
  final String city;
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  static const routeName = '/chat';

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with SingleTickerProviderStateMixin {
  final _api = ApiService();
  final _recorder = AudioRecorder();
  final _player = AudioPlayer();
  late final AnimationController _pulseController;
  late final AnimationController _waveController;
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  Timer? _silenceTimer;

  bool _isRecording = false;
  bool _isVoiceProcessing = false;
  bool _isSpeaking = false;
  bool _isStoppingRecording = false;
  int? _sessionId;
  ChatArgs? _chatArgs;
  DateTime? _recordingStartedAt;
  DateTime? _lastVoiceDetectedAt;

  static const double _speechThresholdDb = -35;
  static const Duration _silenceTimeout = Duration(seconds: 3);
  static const Duration _minRecordingBeforeAutoStop = Duration(milliseconds: 1500);

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat();

    _player.onPlayerStateChanged.listen((state) {
      if (!mounted) return;
      setState(() {
        _isSpeaking = state == PlayerState.playing;
      });
    });
  }

  @override
  void dispose() {
    _silenceTimer?.cancel();
    _amplitudeSubscription?.cancel();
    _pulseController.dispose();
    _waveController.dispose();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _toggleVoice(ChatArgs args) async {
    if (_isVoiceProcessing) return;

    if (_isSpeaking) {
      await _player.stop();
      if (!mounted) return;
      setState(() => _isSpeaking = false);
      await _startRecording();
      return;
    }

    if (!_isRecording) {
      await _startRecording();
      return;
    }

    await _stopAndSendRecording(args, isAutoStop: false);
  }

  Future<void> _startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Mikrofon izni gerekli.')),
      );
      return;
    }

    await _amplitudeSubscription?.cancel();
    _silenceTimer?.cancel();

    await _recorder.start(path: '');
    final now = DateTime.now();
    setState(() {
      _isRecording = true;
      _recordingStartedAt = now;
      _lastVoiceDetectedAt = now;
    });

    _amplitudeSubscription = _recorder.onAmplitudeChanged(const Duration(milliseconds: 250)).listen(
      (amp) {
        if (!_isRecording) return;
        if (amp.current > _speechThresholdDb) {
          _lastVoiceDetectedAt = DateTime.now();
        }
      },
    );

    _silenceTimer = Timer.periodic(const Duration(milliseconds: 600), (timer) {
      if (!_isRecording || _isStoppingRecording) return;
      final startedAt = _recordingStartedAt;
      final lastVoiceAt = _lastVoiceDetectedAt;
      if (startedAt == null || lastVoiceAt == null) return;

      final elapsed = DateTime.now().difference(startedAt);
      final silentFor = DateTime.now().difference(lastVoiceAt);
      if (elapsed >= _minRecordingBeforeAutoStop && silentFor >= _silenceTimeout) {
        _stopAndSendRecording(_chatArgs!, isAutoStop: true);
      }
    });
  }

  Future<void> _stopAndSendRecording(ChatArgs args, {required bool isAutoStop}) async {
    if (_isStoppingRecording) return;
    _isStoppingRecording = true;

    _silenceTimer?.cancel();
    _silenceTimer = null;
    await _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;

    final filePath = await _recorder.stop();
    if (mounted) {
      setState(() {
        _isRecording = false;
      });
    }
    if (filePath == null) {
      _isStoppingRecording = false;
      return;
    }

    final audioFile = File(filePath);
    if (!audioFile.existsSync()) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ses kaydı bulunamadı.')),
        );
      }
      _isStoppingRecording = false;
      return;
    }

    if (mounted) {
      setState(() => _isVoiceProcessing = true);
    }
    try {
      final response = await _api.sendVoiceMessage(
        audioFile: audioFile,
        userName: args.userName,
        age: args.age,
        gender: args.gender,
        profession: args.profession,
        city: args.city,
        sessionId: _sessionId,
      );

      setState(() {
        _sessionId = response.sessionId ?? _sessionId;
      });

      if (response.audioBase64 != null && response.audioBase64!.isNotEmpty) {
        final bytes = base64Decode(response.audioBase64!);
        await _player.stop();
        await _player.play(BytesSource(bytes), volume: 1.0);
      } else if (response.ttsError != null && response.ttsError!.isNotEmpty && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Seslendirilemedi: ${response.ttsError}')),
        );
      }
      if (isAutoStop && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Sessizlik algılandı, kayıt otomatik gönderildi.')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sesli işlem hatası: $e')),
      );
    } finally {
      if (mounted) setState(() => _isVoiceProcessing = false);
      _isStoppingRecording = false;
    }
  }

  String get _statusText {
    if (_isRecording) return 'Dinliyorum...';
    if (_isVoiceProcessing) return 'Dusunuyorum...';
    if (_isSpeaking) return 'Konusuyorum... Dokunursan keserim.';
    return 'Mikrofona dokun ve konus';
  }

  Color get _orbColor {
    if (_isRecording) return const Color(0xFF00BCD4);
    if (_isVoiceProcessing) return const Color(0xFFFFB300);
    if (_isSpeaking) return const Color(0xFF7C4DFF);
    return const Color(0xFF5C6BC0);
  }

  IconData get _centerIcon {
    if (_isRecording) return Icons.graphic_eq;
    if (_isVoiceProcessing) return Icons.psychology_alt;
    if (_isSpeaking) return Icons.volume_up;
    return Icons.mic_none;
  }

  @override
  Widget build(BuildContext context) {
    _chatArgs ??= (ModalRoute.of(context)?.settings.arguments as ChatArgs?) ??
        ChatArgs(
          userId: null,
          userName: 'Kullanıcı',
          age: 0,
          gender: 'Belirtilmedi',
          profession: '',
          city: '',
        );
    final safeArgs = _chatArgs!;

    return Scaffold(
      appBar: AppBar(
        title: Text('Merhaba, ${safeArgs.userName}'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Çıkış',
            onPressed: () async {
              await _api.logout();
              if (!mounted) return;
              Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
            },
          ),
          IconButton(
            icon: const Icon(Icons.person),
            tooltip: 'Profilim',
            onPressed: safeArgs.userId == null
                ? null
                : () async {
                    AuthUser initialProfile;
                    try {
                      initialProfile = await _api.getUserProfile(safeArgs.userId!);
                    } catch (_) {
                      initialProfile = AuthUser(
                        id: safeArgs.userId,
                        displayName: safeArgs.userName,
                        age: safeArgs.age,
                        gender: safeArgs.gender,
                        profession: safeArgs.profession,
                        city: safeArgs.city,
                        maritalStatus: 'Belirtilmedi',
                        childCount: 0,
                        chronicIllness: '',
                        traumaSummary: '',
                        avatar: 'default',
                      );
                    }

                    final updated = await Navigator.of(context).push<AuthUser>(
                      MaterialPageRoute(
                        builder: (_) => ProfileScreen(
                          userId: safeArgs.userId!,
                          initialUser: initialProfile,
                        ),
                      ),
                    );
                    if (updated == null || !mounted) return;
                    setState(() {
                      _chatArgs = ChatArgs(
                        userId: updated.id,
                        userName: updated.displayName,
                        age: updated.age,
                        gender: updated.gender,
                        profession: updated.profession,
                        city: updated.city,
                      );
                    });
                  },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Center(
              child: AnimatedBuilder(
                animation: Listenable.merge([_pulseController, _waveController]),
                builder: (context, _) {
                  final pulse = 1 + (_pulseController.value * 0.14);
                  final auraScale = (_isRecording || _isSpeaking || _isVoiceProcessing) ? pulse : 1.0;
                  return Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Transform.scale(
                        scale: auraScale,
                        child: Container(
                          width: 220,
                          height: 220,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [
                                _orbColor.withValues(alpha: 0.18),
                                _orbColor.withValues(alpha: 0.04),
                              ],
                            ),
                          ),
                          child: Center(
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 350),
                              width: (_isRecording || _isSpeaking) ? 140 : 125,
                              height: (_isRecording || _isSpeaking) ? 140 : 125,
                              decoration: BoxDecoration(
                                color: _orbColor,
                                shape: BoxShape.circle,
                                boxShadow: [
                                  BoxShadow(
                                    color: _orbColor.withValues(alpha: 0.50),
                                    blurRadius: 28,
                                    spreadRadius: 4,
                                  ),
                                ],
                              ),
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  Icon(_centerIcon, color: Colors.white, size: 44),
                                  if (_isRecording || _isSpeaking)
                                    _FakeWaveformBars(progress: _waveController.value),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 26),
                      Text(
                        _statusText,
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 18),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _isVoiceProcessing ? null : () => _toggleVoice(safeArgs),
                  icon: _isVoiceProcessing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(_isRecording
                          ? Icons.stop_circle
                          : _isSpeaking
                              ? Icons.stop
                              : Icons.mic),
                  label: Text(
                    _isRecording
                        ? 'Kaydi Bitir ve Gonder'
                        : _isSpeaking
                            ? 'Botu Kes ve Konus'
                            : 'Konusmaya Basla',
                  ),
                  style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FakeWaveformBars extends StatelessWidget {
  const _FakeWaveformBars({required this.progress});

  final double progress;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 92,
      height: 92,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(7, (i) {
          final value = math.sin((progress * 2 * math.pi) + (i * 0.55)).abs();
          final height = 10 + (value * 26);
          return Container(
            width: 6,
            height: height,
            margin: const EdgeInsets.symmetric(horizontal: 2),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.90),
              borderRadius: BorderRadius.circular(8),
            ),
          );
        }),
      ),
    );
  }
}
