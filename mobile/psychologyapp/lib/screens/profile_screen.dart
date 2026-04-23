import 'package:flutter/material.dart';

import '../models/auth_models.dart';
import '../services/api_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.userId,
    required this.initialUser,
  });

  final int userId;
  final AuthUser initialUser;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _api = ApiService();

  late TextEditingController _displayNameController;
  late TextEditingController _ageController;
  late TextEditingController _professionController;
  late TextEditingController _cityController;
  late TextEditingController _maritalStatusController;
  late TextEditingController _childCountController;
  late TextEditingController _chronicIllnessController;
  late TextEditingController _traumaSummaryController;
  late TextEditingController _avatarController;
  late String _gender;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    final u = widget.initialUser;
    _displayNameController = TextEditingController(text: u.displayName);
    _ageController = TextEditingController(text: u.age.toString());
    _professionController = TextEditingController(text: u.profession);
    _cityController = TextEditingController(text: u.city);
    _maritalStatusController = TextEditingController(text: u.maritalStatus);
    _childCountController = TextEditingController(text: u.childCount.toString());
    _chronicIllnessController = TextEditingController(text: u.chronicIllness);
    _traumaSummaryController = TextEditingController(text: u.traumaSummary);
    _avatarController = TextEditingController(text: u.avatar);
    _gender = u.gender;
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    _ageController.dispose();
    _professionController.dispose();
    _cityController.dispose();
    _maritalStatusController.dispose();
    _childCountController.dispose();
    _chronicIllnessController.dispose();
    _traumaSummaryController.dispose();
    _avatarController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    try {
      final updated = await _api.updateUserProfile(
        userId: widget.userId,
        profile: widget.initialUser.copyWith(
          displayName: _displayNameController.text.trim(),
          age: int.tryParse(_ageController.text.trim()) ?? 0,
          gender: _gender,
          profession: _professionController.text.trim(),
          city: _cityController.text.trim(),
          maritalStatus: _maritalStatusController.text.trim(),
          childCount: int.tryParse(_childCountController.text.trim()) ?? 0,
          chronicIllness: _chronicIllnessController.text.trim(),
          traumaSummary: _traumaSummaryController.text.trim(),
          avatar: _avatarController.text.trim().isEmpty ? "default" : _avatarController.text.trim(),
        ),
      );
      if (!mounted) return;
      Navigator.of(context).pop(updated);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Profil kaydedilemedi: $e')),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Profilim')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              _input(_displayNameController, 'Ad Soyad'),
              _input(_ageController, 'Yaş', keyboardType: TextInputType.number),
              DropdownButtonFormField<String>(
                value: _gender,
                decoration: const InputDecoration(labelText: 'Cinsiyet'),
                items: const [
                  DropdownMenuItem(value: 'Belirtilmedi', child: Text('Belirtilmedi')),
                  DropdownMenuItem(value: 'Kadın', child: Text('Kadın')),
                  DropdownMenuItem(value: 'Erkek', child: Text('Erkek')),
                ],
                onChanged: (v) => setState(() => _gender = v ?? 'Belirtilmedi'),
              ),
              const SizedBox(height: 12),
              _input(_professionController, 'Meslek'),
              _input(_cityController, 'Şehir'),
              _input(_maritalStatusController, 'Medeni Durum'),
              _input(_childCountController, 'Çocuk Sayısı', keyboardType: TextInputType.number),
              _input(_chronicIllnessController, 'Kronik Rahatsızlık'),
              _input(_traumaSummaryController, 'Travma Özeti'),
              _input(_avatarController, 'Avatar (URL veya anahtar)'),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _loading ? null : _save,
                  child: _loading
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Profili Kaydet'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _input(
    TextEditingController controller,
    String label, {
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        keyboardType: keyboardType,
        validator: (value) {
          if (label == 'Ad Soyad' && (value == null || value.trim().isEmpty)) {
            return 'Ad Soyad zorunlu';
          }
          return null;
        },
        decoration: InputDecoration(
          labelText: label,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
    );
  }
}
