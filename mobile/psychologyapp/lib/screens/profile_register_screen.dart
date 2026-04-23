import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../core/config/app_config.dart';
import '../models/auth_models.dart';
import '../services/api_service.dart';
import 'chat_screen.dart';

class ProfileRegisterScreen extends StatefulWidget {
  const ProfileRegisterScreen({super.key});

  @override
  State<ProfileRegisterScreen> createState() => _ProfileRegisterScreenState();
}

class _ProfileRegisterScreenState extends State<ProfileRegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _displayNameController = TextEditingController();
  final _ageController = TextEditingController(text: '25');
  final _professionController = TextEditingController();
  final _cityController = TextEditingController();
  final _api = ApiService();
  late final GoogleSignIn _googleSignIn;

  String _gender = 'Belirtilmedi';
  bool _isLoading = false;
  bool _isLoginMode = false;

  @override
  void initState() {
    super.initState();
    _googleSignIn = AppConfig.googleServerClientId.isEmpty
        ? GoogleSignIn(scopes: const ['email', 'profile'])
        : GoogleSignIn(
            scopes: const ['email', 'profile'],
            serverClientId: AppConfig.googleServerClientId,
          );
    _tryRestoreSession();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _displayNameController.dispose();
    _ageController.dispose();
    _professionController.dispose();
    _cityController.dispose();
    super.dispose();
  }

  Future<void> _tryRestoreSession() async {
    setState(() => _isLoading = true);
    try {
      await _api.initSessionFromStorage();
      final user = _api.currentUser;
      if (user == null || user.id == null) return;
      final refreshed = await _api.getUserProfile(user.id!);
      if (!mounted) return;
      _goToChat(refreshed);
    } catch (_) {
      await _api.logout();
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _goToChat(AuthUser authUser) {
    Navigator.of(context).pushReplacementNamed(
      ChatScreen.routeName,
      arguments: ChatArgs(
        userId: authUser.id,
        userName: authUser.displayName,
        age: authUser.age,
        gender: authUser.gender,
        profession: authUser.profession,
        city: authUser.city,
      ),
    );
  }

  Future<void> _registerAndContinue() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);

    try {
      final authResult = await _api.register(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
        displayName: _displayNameController.text.trim(),
        age: int.tryParse(_ageController.text.trim()) ?? 0,
        gender: _gender,
        profession: _professionController.text.trim(),
        city: _cityController.text.trim(),
      );
      if (!mounted) return;
      _goToChat(authResult.user);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Kayıt başarısız: $e')),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _loginAndContinue() async {
    if (_usernameController.text.trim().isEmpty || _passwordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Kullanıcı adı ve şifre zorunlu')),
      );
      return;
    }
    setState(() => _isLoading = true);

    try {
      final authResult = await _api.login(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
      );
      if (!mounted) return;
      _goToChat(authResult.user);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Giriş başarısız: $e')),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _googleLoginAndContinue() async {
    setState(() => _isLoading = true);
    try {
      final account = await _googleSignIn.signIn();
      if (account == null) return;
      final auth = await account.authentication;
      final idToken = auth.idToken;
      if (idToken == null || idToken.isEmpty) {
        throw Exception('Google idToken alınamadı. Google OAuth ayarlarını kontrol et.');
      }

      final authResult = await _api.loginWithGoogle(idToken: idToken);
      if (!mounted) return;
      _goToChat(authResult.user);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Google girişi başarısız: $e')),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF1E1F3B), Color(0xFF4A4E8C)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: const [BoxShadow(blurRadius: 20, color: Colors.black26)],
                ),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Profil / Kayıt',
                        style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _isLoginMode
                            ? 'Hesabına giriş yapıp sohbete devam et.'
                            : 'Birkaç bilgi gir, sohbeti kişiselleştirelim.',
                      ),
                      const SizedBox(height: 12),
                      SegmentedButton<bool>(
                        showSelectedIcon: false,
                        segments: const [
                          ButtonSegment<bool>(value: false, label: Text('Kayıt')),
                          ButtonSegment<bool>(value: true, label: Text('Giriş')),
                        ],
                        selected: {_isLoginMode},
                        onSelectionChanged: (selection) {
                          setState(() => _isLoginMode = selection.first);
                        },
                      ),
                      const SizedBox(height: 20),
                      _buildInput(_usernameController, 'Kullanıcı Adı'),
                      _buildInput(_passwordController, 'Şifre', obscureText: true),
                      if (!_isLoginMode) ...[
                        _buildInput(_displayNameController, 'Görünen İsim'),
                        _buildInput(_ageController, 'Yaş', keyboardType: TextInputType.number),
                        _buildInput(_professionController, 'Meslek'),
                        _buildInput(_cityController, 'Şehir'),
                        const SizedBox(height: 8),
                        DropdownButtonFormField<String>(
                          value: _gender,
                          decoration: const InputDecoration(labelText: 'Cinsiyet'),
                          items: const [
                            DropdownMenuItem(value: 'Belirtilmedi', child: Text('Belirtilmedi')),
                            DropdownMenuItem(value: 'Kadın', child: Text('Kadın')),
                            DropdownMenuItem(value: 'Erkek', child: Text('Erkek')),
                          ],
                          onChanged: (value) => setState(() => _gender = value ?? 'Belirtilmedi'),
                        ),
                      ],
                      const SizedBox(height: 20),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: _isLoading
                              ? null
                              : () {
                                  if (_isLoginMode) {
                                    _loginAndContinue();
                                  } else {
                                    _registerAndContinue();
                                  }
                                },
                          child: _isLoading
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : Text(_isLoginMode ? 'Giriş Yap' : 'Kaydet ve Sohbete Geç'),
                        ),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: _isLoading ? null : _googleLoginAndContinue,
                          icon: const Icon(Icons.g_mobiledata, size: 28),
                          label: const Text('Google ile Devam Et'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInput(
    TextEditingController controller,
    String label, {
    bool obscureText = false,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        obscureText: obscureText,
        keyboardType: keyboardType,
        validator: (value) {
          if (!_isLoginMode && (value == null || value.trim().isEmpty)) {
            return '$label zorunlu';
          }
          return null;
        },
        decoration: InputDecoration(
          labelText: label,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
    );
  }
}
