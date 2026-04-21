import 'package:flutter/material.dart';

import 'screens/chat_screen.dart';
import 'screens/profile_register_screen.dart';

void main() {
  runApp(const PsikolojiApp());
}

class PsikolojiApp extends StatelessWidget {
  const PsikolojiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Psikoloji App',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF5C6BC0)),
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const ProfileRegisterScreen(),
        ChatScreen.routeName: (context) => const ChatScreen(),
      },
    );
  }
}
