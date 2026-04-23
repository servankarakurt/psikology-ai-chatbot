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
