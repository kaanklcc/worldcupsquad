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
        throw new Error(data.detail || 'Giriş bilgileri hatalı veya kayıt yok.');
      }
      
      onLoginSuccess(data.username, data.token);
    } catch (err: any) {
      setErrorMsg(err.message || 'Sunucuya bağlanılamadı.');
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
      
      setSuccessMsg('Menajer kaydı başarılı! Şimdi şifrenizle giriş yapabilirsiniz.');
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
      
      setSuccessMsg('Şifreniz başarıyla sıfırlandı! Yeni şifrenizle giriş yapabilirsiniz.');
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
    /* Full-screen pitch-bg background */
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pitch-bg rounded-none border-none overflow-hidden select-none">
      {/* Crisp White pitch field lines layer */}
      <div className="absolute inset-0 pitch-lines opacity-25 pointer-events-none scale-105"></div>
      
      {/* Dark semi-transparent vignette/backdrop overlay */}
      <div className="absolute inset-0 bg-black/55 backdrop-blur-[3px] z-0"></div>

      {/* Thematic World Cup Auth Card */}
      <div className="relative z-10 w-full max-w-md bg-slate-950/90 border border-slate-800 rounded-2xl p-6 shadow-[0_15px_50px_rgba(0,0,0,0.8)] overflow-hidden flex flex-col gap-5 text-slate-300 backdrop-blur-md">
        
        {/* World Cup Trophy Header Logo */}
        <div className="flex flex-col items-center gap-1.5">
          <div className="h-16 w-16 rounded-full border-2 border-amber-400 bg-amber-400/10 flex items-center justify-center drop-shadow-[0_0_15px_rgba(245,158,11,0.5)]">
            <span className="material-symbols-outlined text-amber-400 text-3xl animate-pulse">trophy</span>
          </div>
          <h2 className="font-display-lg text-2xl uppercase tracking-wider text-slate-100 mt-2 font-bold flex items-center gap-2">
            <span>FIFA WORLD CUP 2026</span>
          </h2>
          <p className="font-mono-jb text-[10px] text-emerald-400 uppercase tracking-widest font-bold">
            ⚽ DUGOUT ACCESS CONTROL
          </p>
        </div>

        {/* Notifications and validation hints */}
        {errorMsg && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs p-3 rounded-lg flex items-center gap-2 animate-shake">
            <span className="material-symbols-outlined text-sm">error</span>
            <span className="font-body text-[11px] leading-tight">{errorMsg}</span>
          </div>
        )}
        {successMsg && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs p-3 rounded-lg flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">check_circle</span>
            <span className="font-body text-[11px] leading-tight">{successMsg}</span>
          </div>
        )}

        {/* ─── Mode: LOGIN ─────────────────────────────────────────────────── */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Menajer Kimliği (Kullanıcı Adı veya E-posta)</label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">person</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Manager adı veya email"
                  className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg py-2.5 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Giriş Şifresi</label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">lock</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••"
                  className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg py-2.5 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="emerald-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2 cursor-pointer"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'DUGOUT GİRİŞİ YAP'}
            </button>

            <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono-jb mt-2">
              <button type="button" onClick={() => { setMode('forgot_step1'); resetMessages(); }} className="hover:text-emerald-400 transition-colors">
                Şifremi Unuttum?
              </button>
              <button type="button" onClick={() => { setMode('register'); resetMessages(); }} className="hover:text-emerald-400 transition-colors font-bold">
                Yeni Menajer Alımı (Kayıt)
              </button>
            </div>
          </form>
        )}

        {/* ─── Mode: REGISTER ──────────────────────────────────────────────── */}
        {mode === 'register' && (
          <form onSubmit={handleRegister} className="flex flex-col gap-3.5 max-h-[400px] overflow-y-auto pr-1 scrollbar-thin">
            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Menajer Adı</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Manager adı"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Menajer E-postası</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="manager@example.com"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Taktik Şifre</label>
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

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Güvenlik Sorusu (Kurtarma için)</label>
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

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Güvenlik Sorusu Cevabı</label>
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
              className="emerald-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2 cursor-pointer"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'YENİ MENAJER SÖZLEŞMESİ İMZALA'}
            </button>

            <div className="text-center text-[10px] text-slate-400 font-mono-jb mt-1">
              Zaten dugout kaydınız var mı?{' '}
              <button type="button" onClick={() => { setMode('login'); resetMessages(); }} className="text-emerald-400 font-bold hover:underline transition-all">
                Giriş Yap
              </button>
            </div>
          </form>
        )}

        {/* ─── Mode: FORGOT STEP 1 ─────────────────────────────────────────── */}
        {mode === 'forgot_step1' && (
          <form onSubmit={handleGetForgotPasswordQuestion} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Menajer Kimliği (Kullanıcı Adı veya E-posta)</label>
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
              className="gold-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2 cursor-pointer"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'GÜVENLİK SORUSUNU DOĞRULA'}
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

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Güvenlik Sorusu Cevabı</label>
              <input
                type="text"
                value={resetAnswer}
                onChange={(e) => setResetAnswer(e.target.value)}
                placeholder="Cevabınız"
                className="bg-slate-950 border border-slate-800 focus:border-emerald-500 focus:ring-0 rounded-lg p-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-mono-jb text-[9px] text-slate-400 uppercase font-bold tracking-wider">Yeni Taktik Şifre</label>
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
              className="gold-gradient font-display-lg text-xs uppercase py-3 rounded-lg shadow-lg hover:brightness-110 transition-all font-bold text-slate-950 flex justify-center items-center gap-2 mt-2 cursor-pointer"
            >
              {loading ? <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span> : 'YENİ ŞİFREYİ AKTİFLEŞTİR'}
            </button>

            <button type="button" onClick={() => { setMode('login'); resetMessages(); }} className="text-center text-[10px] text-slate-400 hover:text-emerald-400 transition-colors font-mono-jb mt-2">
              İptal et ve Giriş Ekranına Dön
            </button>
          </form>
        )}

        {/* Thematic Footer badge inside card */}
        <div className="border-t border-slate-800 pt-3 text-center text-[9px] text-slate-500 font-mono-jb uppercase tracking-wider">
          🏆 Official 2026 World Cup™ Dugout Interface
        </div>

      </div>
    </div>
  );
}
