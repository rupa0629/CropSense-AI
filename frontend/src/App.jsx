import { useCallback, useEffect, useMemo, useState } from "react";
import {
  askChatbot,
  fetchWeather,
  forgotPassword,
  getAdminOverview,
  getAdminUsers,
  getDashboard,
  getHistory,
  getMe,
  loginUser,
  logoutCurrentSession,
  predictImage,
  registerUser,
  resetPassword,
} from "./api";
import "./App.css";

const navBase = ["Dashboard", "Upload", "Results", "Weather", "Chatbot", "Summary"];

function App() {
  const [auth, setAuth] = useState({ loading: true, user: null });
  const [active, setActive] = useState("Dashboard");
  const [dashboard, setDashboard] = useState({ counts: null, recent: [] });
  const [history, setHistory] = useState([]);
  const [adminOverview, setAdminOverview] = useState(null);
  const [adminUsers, setAdminUsers] = useState([]);
  const [uploadFile, setUploadFile] = useState(null);
  const [result, setResult] = useState(null);
  const [weather, setWeather] = useState(null);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState([{ role: "bot", text: "Hello. I am your AI farming assistant." }]);
  const [isPredicting, setIsPredicting] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  const isAdmin = auth.user?.role === "admin";
  const navItems = isAdmin ? [...navBase, "Admin"] : navBase;

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        setAuth({ loading: false, user: me.user });
        await refreshAll();
      } catch {
        setAuth({ loading: false, user: null });
      }
    })();
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  const refreshAll = async () => {
    try {
      const d = await getDashboard();
      setDashboard({ counts: d.counts, recent: d.recent || [] });
      const h = await getHistory(30);
      setHistory(h.history || []);
    } catch {
      // ignore refresh failures
    }
  };

  const loadAdmin = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const ov = await getAdminOverview();
      const us = await getAdminUsers();
      setAdminOverview(ov.overview);
      setAdminUsers(us.users || []);
    } catch (error) {
      console.error(error);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (active === "Admin") loadAdmin();
  }, [active, loadAdmin]);

  if (auth.loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-100">
        <div className="flex flex-col items-center gap-4 rounded-3xl bg-white/90 p-10 shadow-2xl dark:bg-slate-900/95">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent"></div>
          <p className="text-lg font-semibold">Loading CropSense AI...</p>
        </div>
      </div>
    );
  }

  if (!auth.user) return <AuthScreen onAuth={setAuth} />;

  const logout = async () => {
    await logoutCurrentSession();
    setAuth({ loading: false, user: null });
  };

  const runPredict = async () => {
    if (!uploadFile) {
      alert("Please upload an image before analyzing.");
      return;
    }

    setIsPredicting(true);
    try {
      const data = await predictImage(uploadFile);
      setResult(data);
      setActive("Results");
      await refreshAll();
    } catch (error) {
      alert(error.message || "Prediction failed.");
    } finally {
      setIsPredicting(false);
    }
  };

  const runWeather = async (location) => {
    try {
      const data = await fetchWeather({ location, save_settings: true });
      setWeather(data.weather);
      await refreshAll();
    } catch (error) {
      alert(error.message || "Weather lookup failed.");
    }
  };

  const sendChat = async () => {
    const question = chatInput.trim();
    if (!question) return;
    setMessages((current) => [...current, { role: "user", text: question }]);
    setChatInput("");

    try {
      const res = await askChatbot(question, {
        latest_prediction: result?.disease || null,
        latest_weather: weather || null,
      });
      setMessages((current) => [...current, { role: "bot", text: res.reply }]);
      await refreshAll();
    } catch (error) {
      setMessages((current) => [...current, { role: "bot", text: `Error: ${error.message}` }]);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-6 rounded-[2rem] border border-slate-200/80 bg-white/85 p-6 shadow-2xl backdrop-blur-xl dark:border-slate-700/70 dark:bg-slate-900/75 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.4em] text-slate-500 dark:text-slate-400">CropSense AI dashboard</p>
            <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">Welcome back, {auth.user.full_name || auth.user.email}</h1>
            <p className="mt-2 max-w-2xl text-slate-600 dark:text-slate-400">Monitor rice crop health, analyze uploads, check weather, and ask the AI assistant with a clean, responsive experience.</p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <button className="btn w-full sm:w-auto" onClick={() => setDarkMode((mode) => !mode)}>{darkMode ? "Light mode" : "Dark mode"}</button>
            <button className="btn-ghost w-full sm:w-auto" onClick={logout}>Logout</button>
            {isAdmin && <button className="btn-secondary w-full sm:w-auto" onClick={() => setActive("Admin")}>Admin</button>}
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <aside className="flex flex-col gap-4 rounded-[2rem] border border-slate-200/80 bg-white/85 p-5 shadow-2xl backdrop-blur-xl dark:border-slate-700/70 dark:bg-slate-900/75">
            <div className="rounded-[1.75rem] bg-gradient-to-br from-emerald-500 to-cyan-500 p-5 text-white shadow-xl">
              <p className="text-xs uppercase tracking-[0.4em] opacity-90">Active workspace</p>
              <h2 className="mt-4 text-2xl font-semibold">Field diagnostics</h2>
              <p className="mt-3 text-sm text-emerald-100/90">Fast, modern, and trustworthy rice crop insights.</p>
            </div>
            <nav className="grid gap-3">
              {navItems.map((item) => (
                <button
                  key={item}
                  className={`rounded-3xl px-5 py-3 text-left text-sm font-medium transition ${active === item ? "bg-emerald-500 text-white shadow" : "bg-slate-100 text-slate-800 hover:bg-slate-200 dark:bg-slate-900/80 dark:text-slate-100 dark:hover:bg-slate-800"}`}
                  onClick={() => setActive(item)}
                >
                  {item}
                </button>
              ))}
            </nav>
            <div className="mt-auto rounded-3xl border border-slate-200/80 bg-slate-50/80 p-5 text-sm text-slate-600 dark:border-slate-700/80 dark:bg-slate-950/60 dark:text-slate-300">
              <p className="font-semibold">Quick tips</p>
              <ul className="mt-3 space-y-2">
                <li>Upload sharp leaf photos</li>
                <li>Check weather before field work</li>
                <li>Use the AI assistant for crop guidance</li>
              </ul>
            </div>
          </aside>

          <main className="flex flex-col gap-6">
            {active === "Dashboard" && <Dashboard dashboard={dashboard} history={history} />}
            {active === "Upload" && <UploadCard uploadFile={uploadFile} setUploadFile={setUploadFile} onPredict={runPredict} isPredicting={isPredicting} />}
            {active === "Results" && <Results result={result} />}
            {active === "Weather" && <Weather onFetch={runWeather} weather={weather} />}
            {active === "Chatbot" && <Chatbot messages={messages} setMessages={setMessages} chatInput={chatInput} setChatInput={setChatInput} onSend={sendChat} />}
            {active === "Summary" && <Summary dashboard={dashboard} result={result} weather={weather} />}
            {active === "Admin" && isAdmin && <AdminPanel overview={adminOverview} users={adminUsers} />}
          </main>
        </div>
      </div>
    </div>
  );
}

function AuthScreen({ onAuth }) {
  const [tab, setTab] = useState("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const login = async () => {
    try {
      const data = await loginUser({ email, password });
      onAuth({ loading: false, user: data.user });
    } catch (error) {
      setMsg(error.message);
    }
  };

  const register = async () => {
    try {
      await registerUser({ full_name: fullName, email, password });
      setMsg("Account created successfully. Please login.");
      setTab("login");
    } catch (error) {
      setMsg(error.message);
    }
  };

  const forgot = async () => {
    try {
      const data = await forgotPassword(email);
      setMsg(`${data.message}${data.reset_token ? ` Token: ${data.reset_token}` : ""}`);
      if (data.reset_token) setResetToken(data.reset_token);
      setTab("reset");
    } catch (error) {
      setMsg(error.message);
    }
  };

  const reset = async () => {
    try {
      const data = await resetPassword(resetToken, newPassword);
      setMsg(data.message);
      setTab("login");
    } catch (error) {
      setMsg(error.message);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-emerald-50 to-slate-100 px-4 py-10 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="mx-auto max-w-3xl rounded-[2rem] bg-white/90 p-8 shadow-2xl backdrop-blur-xl dark:bg-slate-900/90">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div>
            <p className="text-sm uppercase tracking-[0.4em] text-emerald-600 dark:text-emerald-300">CropSense AI</p>
            <h2 className="mt-4 text-4xl font-semibold text-slate-900 dark:text-slate-100">Secure access to your AI dashboard</h2>
            <p className="mt-4 text-slate-600 dark:text-slate-400">Sign in, create an account, or reset your password to begin crop analysis and farm recommendations.</p>
          </div>

          <div className="rounded-[2rem] border border-slate-200/80 bg-slate-50 p-6 dark:border-slate-700/80 dark:bg-slate-950/70">
            <div className="flex gap-2 rounded-full bg-slate-200/60 p-1 text-sm font-medium text-slate-700 dark:bg-slate-800/60 dark:text-slate-200">
              {['login', 'register', 'reset'].map((item) => (
                <button key={item} className={`auth-tab flex-1 rounded-full px-3 py-2 ${tab === item ? 'active' : ''}`} onClick={() => { setTab(item); setMsg(''); }}>
                  {item === 'login' ? 'Login' : item === 'register' ? 'Register' : 'Reset'}
                </button>
              ))}
            </div>

            <div className="mt-6 space-y-4">
              {tab === 'register' && <input className="field w-full" placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />}
              <input className="field w-full" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
              {tab !== 'reset' && <input className="field w-full" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />}
              {tab === 'reset' && (
                <>
                  <button className="btn w-full" onClick={forgot}>Send reset token</button>
                  <input className="field w-full" placeholder="Reset token" value={resetToken} onChange={(e) => setResetToken(e.target.value)} />
                  <input className="field w-full" type="password" placeholder="New password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                </>
              )}
            </div>

            <div className="mt-6 grid gap-3">
              {tab === 'login' && <button className="btn w-full" onClick={login}>Login</button>}
              {tab === 'register' && <button className="btn w-full" onClick={register}>Create account</button>}
              {tab === 'reset' && <button className="btn w-full" onClick={reset}>Reset password</button>}
              {tab === 'login' && <button className="btn-ghost w-full" onClick={forgot}>Forgot password?</button>}
            </div>

            {msg && <div className="alert-banner mt-4">{msg}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Dashboard({ dashboard, history }) {
  const counts = dashboard.counts || { analysis_count: 0, weather_count: 0, chat_count: 0 };

  return (
    <>
      <section className="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
        <div className="glass-card p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="section-title">Farm insights</p>
              <h2 className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">Rice disease monitoring made simple</h2>
              <p className="mt-4 max-w-2xl text-slate-600 dark:text-slate-400">Track crop health, weather guidance, and AI-powered recommendations in one modern dashboard.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <span className="status-pill mild">Ready to analyze</span>
              <span className="status-pill moderate">Responsive</span>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-1">
          <Metric title="Analyses" value={counts.analysis_count} description="Crop scans completed" />
          <Metric title="Weather" value={counts.weather_count} description="Weather checks performed" />
          <Metric title="Chat" value={counts.chat_count} description="AI assistant questions" />
        </div>
      </section>

      <section className="glass-card p-8">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Recent analysis</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Latest crop predictions and confidence levels.</p>
          </div>
          <span className="text-sm text-slate-500 dark:text-slate-400">Updated today</span>
        </div>

        <div className="mt-6 overflow-hidden rounded-[1.75rem] border border-slate-200/80 dark:border-slate-700/80">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-100/80 text-slate-500 dark:bg-slate-800/70 dark:text-slate-300">
              <tr>
                <th className="px-6 py-4">Image</th>
                <th className="px-6 py-4">Disease</th>
                <th className="px-6 py-4">Confidence</th>
                <th className="px-6 py-4">Severity</th>
                <th className="px-6 py-4">Date</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-slate-950">
              {history.length ? history.map((entry, index) => (
                <tr key={index} className="border-t border-slate-200/80 dark:border-slate-700/80">
                  <td className="px-6 py-4">{entry.image_name || 'Photo'}</td>
                  <td className="px-6 py-4">{entry.disease || '—'}</td>
                  <td className="px-6 py-4">{Math.round((entry.confidence || 0) * 100)}%</td>
                  <td className="px-6 py-4">{entry.severity || '—'}</td>
                  <td className="px-6 py-4">{entry.created_at ? new Date(entry.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-slate-500 dark:text-slate-400">No analysis history available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Metric({ title, value, description }) {
  return (
    <div className="glass-card p-8">
      <p className="section-title">{title}</p>
      <h2 className="mt-4 text-4xl font-semibold text-slate-900 dark:text-slate-100">{value ?? 0}</h2>
      <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">{description}</p>
    </div>
  );
}

function UploadCard({ uploadFile, setUploadFile, onPredict, isPredicting }) {
  const uploadPreview = useMemo(() => (uploadFile ? URL.createObjectURL(uploadFile) : ""), [uploadFile]);

  useEffect(() => {
    if (!uploadPreview) return undefined;
    return () => URL.revokeObjectURL(uploadPreview);
  }, [uploadPreview]);

  const handleFile = (file) => {
    if (file && file.type.startsWith("image/")) {
      setUploadFile(file);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    if (event.dataTransfer.files.length) {
      handleFile(event.dataTransfer.files[0]);
    }
  };

  return (
    <section className="grid gap-6 xl:grid-cols-[1.45fr_0.75fr]">
      <div className="glass-card p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="section-title">Upload</p>
            <h3 className="mt-3 text-2xl font-semibold text-slate-900 dark:text-slate-100">Upload a leaf photo</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Submit a clear image and let the AI provide a diagnosis instantly.</p>
          </div>
          <span className="status-pill mild">Fast inference</span>
        </div>

        <label
          className="upload-box mt-8"
          htmlFor="crop-image-upload"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <span className="upload-title">Drag and drop an image</span>
          <span className="upload-hint">or click here to choose a PNG, JPG, or WEBP file</span>
          {uploadFile && <span className="upload-filename">Selected: {uploadFile.name}</span>}
        </label>
        <input
          id="crop-image-upload"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="visually-hidden"
          onChange={(event) => handleFile(event.target.files?.[0])}
        />

        {uploadPreview ? (
          <img className="mt-8 w-full rounded-[1.75rem] border border-slate-200/80 object-cover dark:border-slate-700/80" src={uploadPreview} alt="Preview" />
        ) : (
          <div className="mt-8 rounded-[1.75rem] border border-dashed border-slate-300/80 bg-slate-100/70 p-10 text-center text-slate-500 dark:border-slate-700/80 dark:bg-slate-950/50 dark:text-slate-400">
            Image preview will appear here.
          </div>
        )}

        <div className="mt-8 grid gap-3 sm:grid-cols-[1fr_auto]">
          <button className="btn w-full" onClick={onPredict} disabled={!uploadFile || isPredicting}>
            {isPredicting ? "Analyzing..." : "Analyze crop"}
          </button>
          <button className="btn-ghost w-full" onClick={() => setUploadFile(null)}>Clear selection</button>
        </div>
      </div>

      <div className="card p-8">
        <div className="section-title">Upload checklist</div>
        <ul className="mt-6 space-y-3 text-sm text-slate-600 dark:text-slate-300">
          <li>Use a sharp, close-up view of the rice leaf.</li>
          <li>Prefer daylight and avoid glare.</li>
          <li>Keep the background simple and uncluttered.</li>
          <li>Focus on the most symptomatic area of the plant.</li>
        </ul>
      </div>
    </section>
  );
}

function Results({ result }) {
  if (!result) {
    return (
      <section className="glass-card p-8">
        <p className="text-slate-600 dark:text-slate-300">No result yet — upload an image and run analysis to get diagnostics, severity, and recommendations.</p>
      </section>
    );
  }

  const confidence = Math.round((result.confidence || 0) * 100);
  const severityLevel = result.severity?.level || "Mild";

  return (
    <section className="grid gap-6 xl:grid-cols-[1.4fr_0.7fr]">
      <div className="glass-card p-8">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="section-title">Analysis result</p>
            <h3 className="mt-3 text-2xl font-semibold text-slate-900 dark:text-slate-100">{result.disease || "Unknown issue"}</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Based on your uploaded photo and the AI model score.</p>
          </div>
          <span className={`status-pill ${severityLevel.toLowerCase()}`}>{severityLevel}</span>
        </div>

        <div className="mt-8 space-y-6">
          <div className="rounded-[1.75rem] bg-slate-50 p-6 dark:bg-slate-950/60">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">Confidence</p>
              <span className="font-semibold text-slate-800 dark:text-slate-100">{confidence}%</span>
            </div>
            <div className="mt-4 h-3 rounded-full bg-slate-200 dark:bg-slate-800">
              <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-cyan-500 to-sky-500" style={{ width: `${confidence}%` }} />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[1.75rem] bg-slate-50 p-6 dark:bg-slate-950/60">
              <h4 className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">Severity guidance</h4>
              <p className="mt-4 text-slate-700 dark:text-slate-200">{result.severity?.advice || "Retake the photo for a clearer diagnosis if needed."}</p>
            </div>
            <div className="rounded-[1.75rem] bg-slate-50 p-6 dark:bg-slate-950/60">
              <h4 className="text-sm uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">Recommended actions</h4>
              <div className="mt-4 space-y-3">
                {(result.fertilizer?.fertiliser || []).map((item, index) => (
                  <div key={index} className="rounded-2xl bg-white/90 p-3 text-sm text-slate-700 shadow-sm dark:bg-slate-900/80 dark:text-slate-200">{item}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Prediction summary</h3>
        <div className="mt-6 space-y-4">
          <SummaryRow label="Disease" value={result.disease || "—"} />
          <SummaryRow label="Method" value={result.method || "AI model"} />
          <SummaryRow label="Confidence" value={`${confidence}%`} />
          <SummaryRow label="Severity" value={severityLevel} />
          <SummaryRow label="Action" value={result.fertilizer?.immediate_action || "Review the recommendation."} />
        </div>
      </div>
    </section>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-[1.75rem] border border-slate-200/80 bg-slate-50 px-5 py-4 dark:border-slate-700/80 dark:bg-slate-950/50">
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
      <span className="font-semibold text-slate-900 dark:text-slate-100">{value}</span>
    </div>
  );
}

function Weather({ onFetch, weather }) {
  const [location, setLocation] = useState("Delhi,IN");

  return (
    <section className="grid gap-6 xl:grid-cols-[1.45fr_0.75fr]">
      <div className="glass-card p-8">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="section-title">Weather</p>
            <h3 className="mt-3 text-2xl font-semibold text-slate-900 dark:text-slate-100">Field conditions at a glance</h3>
          </div>
          <span className="status-pill mild">Real-time</span>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-[1.8fr_1fr]">
          <input className="field" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City,Country code" />
          <button className="btn w-full" onClick={() => onFetch(location)}>Fetch weather</button>
        </div>

        {weather && (
          <div className="weather-grid mt-8 grid gap-4 sm:grid-cols-2">
            <div className="weather-card rounded-[1.75rem] border border-slate-200/80 bg-slate-50 p-6 dark:border-slate-700/80 dark:bg-slate-950/50">
              <h4 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{weather.location}</h4>
              <p className="mt-2 text-slate-600 dark:text-slate-400">{weather.description}</p>
              <p className="mt-4 text-3xl font-semibold text-slate-900 dark:text-white">{weather.temperature}°C</p>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Humidity {weather.humidity}% · Wind {weather.wind_speed}</p>
            </div>
            <div className="weather-card rounded-[1.75rem] border border-slate-200/80 bg-slate-50 p-6 dark:border-slate-700/80 dark:bg-slate-950/50">
              <h4 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Advisory</h4>
              <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-300">
                {(weather.advisories || []).map((item, index) => (<li key={index}>• {item}</li>))}
              </ul>
            </div>
          </div>
        )}
      </div>

      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Weather guidance</h3>
        <p className="mt-4 text-slate-600 dark:text-slate-300">Weather awareness can help reduce crop stress and guide treatment timing.</p>
      </div>
    </section>
  );
}

function Chatbot({ messages, setMessages, chatInput, setChatInput, onSend }) {
  const quickPrompts = [
    "How to treat Leaf Blast?",
    "Best fertilizer for Brown Spot?",
    "When should I spray fungicide?",
  ];

  return (
    <section className="grid gap-6 xl:grid-cols-[1.4fr_0.75fr]">
      <div className="glass-card p-8 flex flex-col">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="section-title">AI assistant</p>
            <h3 className="mt-3 text-2xl font-semibold text-slate-900 dark:text-slate-100">Ask your farm expert</h3>
          </div>
          <span className="status-pill mild">Interactive</span>
        </div>

        <div className="chat-box mt-6 flex-1 overflow-y-auto rounded-[1.75rem] border border-slate-200/80 bg-slate-50 p-6 dark:border-slate-700/80 dark:bg-slate-950/50">
          {messages.map((message, index) => (
            <div key={index} className={`bubble ${message.role} mb-4 max-w-[85%] rounded-3xl px-5 py-4 ${message.role === 'user' ? 'ml-auto bg-emerald-500 text-white' : 'bg-white text-slate-800 shadow dark:bg-slate-900/80 dark:text-slate-100'}`}>
              <p>{message.text}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-[1fr_auto]">
          <input className="field" value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="Type a question" />
          <button className="btn w-full sm:w-auto" onClick={onSend}>Send</button>
        </div>
      </div>

      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Quick prompts</h3>
        <div className="mt-5 grid gap-3">
          {quickPrompts.map((prompt) => (
            <button key={prompt} className="btn-ghost text-left" onClick={() => { setMessages((current) => [...current, { role: 'user', text: prompt }]); setChatInput(prompt); }}>
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function Summary({ dashboard, result, weather }) {
  return (
    <section className="grid gap-6 xl:grid-cols-3">
      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">App snapshot</h3>
        <div className="mt-6 space-y-4">
          <SummaryRow label="Analyses" value={dashboard.counts?.analysis_count ?? 0} />
          <SummaryRow label="Weather checks" value={dashboard.counts?.weather_count ?? 0} />
          <SummaryRow label="Chat interactions" value={dashboard.counts?.chat_count ?? 0} />
        </div>
      </div>

      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Last diagnosis</h3>
        <div className="mt-6 space-y-4">
          <SummaryRow label="Disease" value={result?.disease || 'N/A'} />
          <SummaryRow label="Severity" value={result?.severity?.level || 'N/A'} />
          <SummaryRow label="Confidence" value={`${Math.round((result?.confidence || 0) * 100)}%`} />
        </div>
      </div>

      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Weather summary</h3>
        <div className="mt-6 space-y-4">
          <SummaryRow label="Condition" value={weather?.description || 'N/A'} />
          <SummaryRow label="Humidity" value={weather?.humidity ? `${weather.humidity}%` : 'N/A'} />
        </div>
      </div>
    </section>
  );
}

function AdminPanel({ overview, users }) {
  return (
    <section className="grid gap-6 xl:grid-cols-[1.4fr_0.8fr]">
      <div className="card p-8">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Admin overview</h3>
        <div className="mt-6 space-y-4">
          <SummaryRow label="Users" value={overview?.users ?? 0} />
          <SummaryRow label="Analyses" value={overview?.analyses ?? 0} />
          <SummaryRow label="Weather checks" value={overview?.weather_checks ?? 0} />
          <SummaryRow label="Chat messages" value={overview?.chat_messages ?? 0} />
        </div>
      </div>

      <div className="card p-8 overflow-auto">
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Users</h3>
        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-100/80 text-slate-500 dark:bg-slate-800/70 dark:text-slate-300">
              <tr>
                <th className="px-6 py-4">ID</th>
                <th className="px-6 py-4">Name</th>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Role</th>
                <th className="px-6 py-4">Created</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-slate-950">
              {users.map((user) => (
                <tr key={user.id} className="border-t border-slate-200/80 dark:border-slate-700/80">
                  <td className="px-6 py-4">{user.id}</td>
                  <td className="px-6 py-4">{user.full_name}</td>
                  <td className="px-6 py-4">{user.email}</td>
                  <td className="px-6 py-4">{user.role}</td>
                  <td className="px-6 py-4">{user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default App;




