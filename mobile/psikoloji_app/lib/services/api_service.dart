import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiService {
  ApiService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  static const _storage = FlutterSecureStorage();
  static const _kAccessToken = 'access_token';
  static const _kRefreshToken = 'refresh_token';
  static const _kCurrentUser = 'current_user';
  static String? _accessToken;
  static String? _refreshToken;
  static AuthUser? _currentUser;

  // Emulator için 10.0.2.2, fiziksel cihaz için bilgisayarın LAN IP'sini kullan.
  static const String _baseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

  Future<void> initSessionFromStorage() async {
    _accessToken = await _storage.read(key: _kAccessToken);
    _refreshToken = await _storage.read(key: _kRefreshToken);
    final userRaw = await _storage.read(key: _kCurrentUser);
    if (userRaw != null && userRaw.isNotEmpty) {
      _currentUser = AuthUser.fromJson(jsonDecode(userRaw) as Map<String, dynamic>);
    }
  }

  AuthUser? get currentUser => _currentUser;

  bool get isSessionAvailable =>
      _accessToken != null && _accessToken!.isNotEmpty && _currentUser != null;

  void setAccessToken(String? token) {
    _accessToken = token;
  }

  void setRefreshToken(String? token) {
    _refreshToken = token;
  }

  Future<void> _persistSession(AuthResult authResult) async {
    _currentUser = authResult.user;
    _accessToken = authResult.accessToken;
    _refreshToken = authResult.refreshToken;
    await _storage.write(key: _kAccessToken, value: _accessToken);
    await _storage.write(key: _kRefreshToken, value: _refreshToken);
    await _storage.write(
      key: _kCurrentUser,
      value: jsonEncode(authResult.user.toJson()),
    );
  }

  Future<void> _clearSession() async {
    _accessToken = null;
    _refreshToken = null;
    _currentUser = null;
    await _storage.delete(key: _kAccessToken);
    await _storage.delete(key: _kRefreshToken);
    await _storage.delete(key: _kCurrentUser);
  }

  Future<AuthResult> register({
    required String username,
    required String password,
    required String displayName,
    required int age,
    required String gender,
    String profession = '',
    String city = '',
  }) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
        'display_name': displayName,
        'age': age,
        'gender': gender,
        'profession': profession,
        'city': city,
      }),
    );

    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Kayıt hatası');
    }

    final user = body['user'] as Map<String, dynamic>? ?? {};
    final token = body['access_token']?.toString();
    final refreshToken = body['refresh_token']?.toString();
    final result = AuthResult(
      user: AuthUser.fromJson(user),
      accessToken: token ?? '',
      refreshToken: refreshToken ?? '',
    );
    await _persistSession(result);
    return result;
  }

  Future<AuthResult> login({
    required String username,
    required String password,
  }) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
      }),
    );

    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Giriş hatası');
    }

    final user = body['user'] as Map<String, dynamic>? ?? {};
    final token = body['access_token']?.toString();
    final refreshToken = body['refresh_token']?.toString();
    final result = AuthResult(
      user: AuthUser.fromJson(user),
      accessToken: token ?? '',
      refreshToken: refreshToken ?? '',
    );
    await _persistSession(result);
    return result;
  }

  Future<AuthResult> loginWithGoogle({required String idToken}) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/auth/google'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'id_token': idToken}),
    );

    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Google girişi hatası');
    }

    final user = body['user'] as Map<String, dynamic>? ?? {};
    final token = body['access_token']?.toString();
    final refreshToken = body['refresh_token']?.toString();
    final result = AuthResult(
      user: AuthUser.fromJson(user),
      accessToken: token ?? '',
      refreshToken: refreshToken ?? '',
    );
    await _persistSession(result);
    return result;
  }

  Future<void> refreshAccessToken() async {
    if (_refreshToken == null || _refreshToken!.isEmpty) {
      throw Exception('Refresh token bulunamadı');
    }

    final response = await _client.post(
      Uri.parse('$_baseUrl/auth/refresh'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh_token': _refreshToken}),
    );

    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Token yenileme hatası');
    }

    _accessToken = body['access_token']?.toString();
    _refreshToken = body['refresh_token']?.toString();
    await _storage.write(key: _kAccessToken, value: _accessToken);
    await _storage.write(key: _kRefreshToken, value: _refreshToken);
  }

  Future<void> logout() async {
    if (_refreshToken != null && _refreshToken!.isNotEmpty) {
      await _client.post(
        Uri.parse('$_baseUrl/auth/logout'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': _refreshToken}),
      );
    }
    await _clearSession();
  }

  Future<AuthUser> getUserProfile(int userId) async {
    final response = await _sendAuthorized(
      (headers) => _client.get(
        Uri.parse('$_baseUrl/users/$userId/profile'),
        headers: headers,
      ),
    );
    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Profil alınamadı');
    }

    final user = body['user'] as Map<String, dynamic>? ?? {};
    final authUser = AuthUser.fromJson(user);
    _currentUser = authUser;
    await _storage.write(key: _kCurrentUser, value: jsonEncode(authUser.toJson()));
    return authUser;
  }

  Future<AuthUser> updateUserProfile({
    required int userId,
    required AuthUser profile,
  }) async {
    final response = await _sendAuthorized(
      (headers) => _client.put(
        Uri.parse('$_baseUrl/users/$userId/profile'),
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'display_name': profile.displayName,
          'age': profile.age,
          'gender': profile.gender,
          'profession': profile.profession,
          'city': profile.city,
          'marital_status': profile.maritalStatus,
          'child_count': profile.childCount,
          'chronic_illness': profile.chronicIllness,
          'trauma_summary': profile.traumaSummary,
          'avatar': profile.avatar,
        }),
      ),
    );

    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Profil güncellenemedi');
    }

    final user = body['user'] as Map<String, dynamic>? ?? {};
    final updated = AuthUser.fromJson(user);
    _currentUser = updated;
    await _storage.write(key: _kCurrentUser, value: jsonEncode(updated.toJson()));
    return updated;
  }

  Future<ChatResult> sendChatMessage({
    required String query,
    int? sessionId,
    required String userName,
    required int age,
    required String gender,
    required String profession,
    required String city,
  }) async {
    final response = await _sendAuthorized(
      (headers) => _client.post(
        Uri.parse('$_baseUrl/chat'),
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'query': query,
          'session_id': sessionId,
          'history': <Map<String, dynamic>>[],
          'k': 3,
          'user_profile': {
            'name': userName,
            'age': age,
            'gender': gender,
            'profession': profession,
            'city': city,
            'marital_status': 'Belirtilmedi',
            'child_count': 0,
            'chronic_illness': '',
            'trauma_summary': '',
          }
        }),
      ),
    );

    final body = _decodeJson(response.body);
    if (response.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Sohbet hatası');
    }

    return ChatResult(
      reply: body['reply']?.toString() ?? '',
      sessionId: body['session_id'] as int?,
      isCrisis: body['is_crisis'] == true,
    );
  }

  Future<MobileChatResult> sendVoiceMessage({
    required File audioFile,
    required String userName,
    required int age,
    required String gender,
    String profession = '',
    String city = '',
    int? sessionId,
  }) async {
    final streamedResponse = await _sendAuthorizedMultipart(
      () async {
        final request = http.MultipartRequest('POST', Uri.parse('$_baseUrl/mobile-chat'))
          ..fields['user_name'] = userName
          ..fields['age'] = age.toString()
          ..fields['gender'] = gender
          ..fields['profession'] = profession
          ..fields['city'] = city;

        final authHeaders = _authHeaders();
        if (authHeaders.isNotEmpty) {
          request.headers.addAll(authHeaders);
        }
        if (sessionId != null) request.fields['session_id'] = sessionId.toString();

        request.files.add(await http.MultipartFile.fromPath('audio_file', audioFile.path));
        return request;
      },
    );
    final responseBody = await streamedResponse.stream.bytesToString();
    final body = _decodeJson(responseBody);

    if (streamedResponse.statusCode >= 400) {
      throw Exception(body['detail'] ?? 'Sesli sohbet hatası');
    }

    return MobileChatResult(
      reply: body['reply']?.toString() ?? '',
      transcript: body['transcript']?.toString() ?? '',
      audioBase64: body['audio_base64']?.toString(),
      sessionId: body['session_id'] as int?,
      ttsError: body['tts_error']?.toString(),
    );
  }

  Map<String, dynamic> _decodeJson(String source) {
    if (source.isEmpty) return {};
    return jsonDecode(source) as Map<String, dynamic>;
  }

  Map<String, String> _authHeaders() {
    if (_accessToken == null || _accessToken!.isEmpty) {
      return {};
    }
    return {'Authorization': 'Bearer $_accessToken'};
  }

  Future<http.Response> _sendAuthorized(
    Future<http.Response> Function(Map<String, String> headers) request,
  ) async {
    final firstResponse = await request(_authHeaders());
    if (firstResponse.statusCode != 401) {
      return firstResponse;
    }

    if (_refreshToken == null || _refreshToken!.isEmpty) {
      return firstResponse;
    }

    try {
      await refreshAccessToken();
    } catch (_) {
      await _clearSession();
      return firstResponse;
    }
    return request(_authHeaders());
  }

  Future<http.StreamedResponse> _sendAuthorizedMultipart(
    Future<http.MultipartRequest> Function() buildRequest,
  ) async {
    final firstRequest = await buildRequest();
    final firstResponse = await firstRequest.send();
    if (firstResponse.statusCode != 401) {
      return firstResponse;
    }

    if (_refreshToken == null || _refreshToken!.isEmpty) {
      return firstResponse;
    }

    try {
      await refreshAccessToken();
    } catch (_) {
      await _clearSession();
      return firstResponse;
    }

    final retryRequest = await buildRequest();
    return retryRequest.send();
  }
}

class AuthResult {
  AuthResult({
    required this.user,
    required this.accessToken,
    required this.refreshToken,
  });

  final AuthUser user;
  final String accessToken;
  final String refreshToken;
}

class AuthUser {
  AuthUser({
    required this.id,
    required this.displayName,
    required this.age,
    required this.gender,
    required this.profession,
    required this.city,
    required this.maritalStatus,
    required this.childCount,
    required this.chronicIllness,
    required this.traumaSummary,
    required this.avatar,
  });

  final int? id;
  final String displayName;
  final int age;
  final String gender;
  final String profession;
  final String city;
  final String maritalStatus;
  final int childCount;
  final String chronicIllness;
  final String traumaSummary;
  final String avatar;

  AuthUser copyWith({
    String? displayName,
    int? age,
    String? gender,
    String? profession,
    String? city,
    String? maritalStatus,
    int? childCount,
    String? chronicIllness,
    String? traumaSummary,
    String? avatar,
  }) {
    return AuthUser(
      id: id,
      displayName: displayName ?? this.displayName,
      age: age ?? this.age,
      gender: gender ?? this.gender,
      profession: profession ?? this.profession,
      city: city ?? this.city,
      maritalStatus: maritalStatus ?? this.maritalStatus,
      childCount: childCount ?? this.childCount,
      chronicIllness: chronicIllness ?? this.chronicIllness,
      traumaSummary: traumaSummary ?? this.traumaSummary,
      avatar: avatar ?? this.avatar,
    );
  }

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: json['id'] as int?,
      displayName: json['display_name']?.toString() ?? 'Kullanıcı',
      age: (json['age'] as num?)?.toInt() ?? 0,
      gender: json['gender']?.toString() ?? 'Belirtilmedi',
      profession: json['profession']?.toString() ?? '',
      city: json['city']?.toString() ?? '',
      maritalStatus: json['marital_status']?.toString() ?? 'Belirtilmedi',
      childCount: (json['child_count'] as num?)?.toInt() ?? 0,
      chronicIllness: json['chronic_illness']?.toString() ?? '',
      traumaSummary: json['trauma_summary']?.toString() ?? '',
      avatar: json['avatar']?.toString() ?? 'default',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'display_name': displayName,
      'age': age,
      'gender': gender,
      'profession': profession,
      'city': city,
      'marital_status': maritalStatus,
      'child_count': childCount,
      'chronic_illness': chronicIllness,
      'trauma_summary': traumaSummary,
      'avatar': avatar,
    };
  }
}

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
