'use client';

import { useState } from 'react';

interface AuthOverlayProps {
  onLoginSuccess: (username: string, token: string) => void;
}

type AuthMode = 'login' | 'register' | 'forgot_step1' | 'forgot_step2';

const SECURITY_QUESTIONS = [
  "İlk evcil hayvanınızın adı nedir?",
  "En sevdiğiniz futbolcunun adı nedir?",
  "Doğduğunuz şehir neresidir?",
  "İlk okul öğretmeninizin soyadı nedir?"
];

export default function AuthOverlay({ onLoginSuccess }: AuthOverlayProps) {
  const [mode, setMode] = useState<AuthMode>('login');
  
  // Form fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState(SECURITY_QUESTIONS[0]);
  const [securityAnswer, setSecurityAnswer] = useState('');
  
  // Forgot password specific fields
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [fetchedQuestion, setFetchedQuestion] = useState('');
  const [resetAnswer, setResetAnswer] = useState('');
  const [newPassword, setNewPassword] = useState('');
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const resetMessages = () => {
    setErrorMsg('');
    setSuccessMsg('');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    if (!username || !password) {
      setErrorMsg('Lütfen tüm alanları doldurun.');
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username_or_email: username,
          password: password
        })
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Giriş yapılamadı.');
      }
      
      onLoginSuccess(data.username, data.token);
    } catch (err: any) {
      setErrorMsg(err.message || 'Sunucu bağlantı hatası.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    if (!username || !email || !password || !securityAnswer) {
      setErrorMsg('Lütfen tüm alanları doldurun.');
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          email,
          password,
          security_question: securityQuestion,
          security_answer: securityAnswer
        })
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Kayıt başarısız.');
      }
      
      setSuccessMsg('Kayıt başarılı! Şimdi giriş yapabilirsiniz.');
      setMode('login');
      setPassword('');
      setSecurityAnswer('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Kayıt sırasında bir hata oluştu.');
    } finally {
      setLoading(false);
    }
  };

  const handleGetForgotPasswordQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    if (!usernameOrEmail) {
      setErrorMsg('Kullanıcı adı veya e-posta girin.');
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/forgot-password-question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username_or_email: usernameOrEmail })
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Kullanıcı bulunamadı.');
      }
      
      setFetchedQuestion(data.security_question);
      setMode('forgot_step2');
    } catch (err: any) {
      setErrorMsg(err.message || 'Bir hata oluştu.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    if (!resetAnswer || !newPassword) {
      setErrorMsg('Lütfen tüm alanları doldurun.');
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username_or_email: usernameOrEmail,
          security_answer: resetAnswer,
          new_password: newPassword
        })
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Şifre sıfırlama başarısız.');
      }
      
      setSuccessMsg('Şifreniz başarıyla sıfırlandı! Şimdi yeni şifrenizle giriş yapın.');
      setMode('login');
      setUsername(usernameOrEmail);
      setPassword('');
      setResetAnswer('');
      setNewPassword('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Şifre sıfırlanamadı.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-lg">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl overflow-hidden flex flex-col gap-6 z-10 text-slate-300">
        
        {/* Header Logo */}
        <div className="flex flex-col items-center gap-2">
          <div className="h-14 w-14 rounded-full border-2 border-emerald-500 bg-emerald-500/10 flex items-center justify-center drop-shadow-[0_0_10px_rgba(16,185,129,0.4)]">
            <span className="material-symbols-outlined text-emerald-500 text-3xl">sports_soccer</span>
          </div>
          <h2 className="font-display-lg text-2xl uppercase tracking-wider text-slate-100 mt-2">
            Auto-Gaffer
          </h2>
          <p className="font-mono-jb text-[10px] text-emerald-400 uppercase tracking-widest">
            Manager Control Center
          </p>
        </div>

        {/* Notifications */}
        {errorMsg && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs p-3 rounded-lg flex items-center gap-2 animate-shake">
            <span className="material-symbols-outlined text-sm">error</span>
            <span>{errorMsg}</span>
          </div>
        )}
        {successMsg && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs p-3 rounded-lg flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">check_circle</span>
            <span>{successMsg}</span>
          </div>
        )}

        {/* ─── Mode: LOGIN ─────────────────────────────────────────────────── */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Kullanıcı Adı veya E-posta</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Manager adı veya email"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Şifre</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="emerald-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'GİRİŞ YAP'}
            </button>

            <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono-jb mt-2">
              <button type="button" onClick={() => { setMode('forgot_step1'); resetMessages(); }} className="hover:text-emerald-400 transition-colors">
                Şifremi Unuttum?
              </button>
              <button type="button" onClick={() => { setMode('register'); resetMessages(); }} className="hover:text-emerald-400 transition-colors font-bold">
                Yeni Hesap Oluştur
              </button>
            </div>
          </form>
        )}

        {/* ─── Mode: REGISTER ──────────────────────────────────────────────── */}
        {mode === 'register' && (
          <form onSubmit={handleRegister} className="flex flex-col gap-3.5 max-h-[450px] overflow-y-auto pr-1 scrollbar-thin">
            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Kullanıcı Adı</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Manager adı"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">E-posta</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="manager@example.com"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Şifre</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 6 karakter"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
              <p className="text-[9px] text-slate-500 font-mono-jb mt-0.5 leading-normal">
                * Şifreniz en az 6 karakter, 1 büyük harf (A-Z), 1 küçük harf (a-z) ve 1 rakam (0-9) içermelidir.
              </p>
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Güvenlik Sorusu (Şifre Kurtarma için)</label>
              <select
                value={securityQuestion}
                onChange={(e) => setSecurityQuestion(e.target.value)}
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-300 outline-none transition-all"
              >
                {SECURITY_QUESTIONS.map((q) => (
                  <option key={q} value={q} className="bg-slate-900">{q}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Güvenlik Sorusu Cevabı</label>
              <input
                type="text"
                value={securityAnswer}
                onChange={(e) => setSecurityAnswer(e.target.value)}
                placeholder="Cevabınız"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="emerald-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'KAYIT OL'}
            </button>

            <div className="text-center text-[10px] text-slate-400 font-mono-jb mt-1">
              Zaten hesabınız var mı?{' '}
              <button type="button" onClick={() => { setMode('login'); resetMessages(); }} className="text-emerald-400 font-bold hover:underline transition-all">
                Giriş Yap
              </button>
            </div>
          </form>
        )}

        {/* ─── Mode: FORGOT STEP 1 ─────────────────────────────────────────── */}
        {mode === 'forgot_step1' && (
          <form onSubmit={handleGetForgotPasswordQuestion} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Kullanıcı Adı veya E-posta</label>
              <input
                type="text"
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
                placeholder="Sıfırlanacak hesabın bilgisi"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="gold-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'GÜVENLİK SORUSUNU GETİR'}
            </button>

            <button type="button" onClick={() => { setMode('login'); resetMessages(); }} className="text-center text-[10px] text-slate-400 hover:text-emerald-400 transition-colors font-mono-jb mt-2">
              İptal et ve Giriş Ekranına Dön
            </button>
          </form>
        )}

        {/* ─── Mode: FORGOT STEP 2 ─────────────────────────────────────────── */}
        {mode === 'forgot_step2' && (
          <form onSubmit={handleResetPassword} className="flex flex-col gap-4">
            <div className="bg-slate-950 border border-slate-800 p-3.5 rounded-lg flex flex-col gap-1">
              <div className="font-mono-jb text-[8px] text-slate-500 uppercase font-bold">Güvenlik Sorunuz:</div>
              <div className="text-sm font-bold text-slate-200">{fetchedQuestion}</div>
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Güvenlik Sorusu Cevabı</label>
              <input
                type="text"
                value={resetAnswer}
                onChange={(e) => setResetAnswer(e.target.value)}
                placeholder="Cevabınız"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono-jb text-[10px] text-slate-400 uppercase">Yeni Şifre</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min 6 karakter"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="gold-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'ŞİFREYİ SIFIRLA'}
            </button>

            <button type="button" onClick={() => { setMode('login'); resetMessages(); }} className="text-center text-[10px] text-slate-400 hover:text-emerald-400 transition-colors font-mono-jb mt-2">
              İptal et ve Giriş Ekranına Dön
            </button>
          </form>
        )}

      </div>
    </div>
  );
}
