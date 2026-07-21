"use client";

import React, { useState, useEffect } from "react";
import { 
  Briefcase, FileText, Mail, Settings, LogOut, CheckCircle2, 
  Search, ShieldAlert, Zap, Loader2, RefreshCw, BarChart2, Eye, EyeOff,
  User, Check, ChevronRight, Send, HelpCircle, Plus, Trash2
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const STAGE_COLORS: Record<string, string> = {
  Discovered: "#5C6A63",
  Saved: "#4C8FF0",
  Applied: "#F0B057",
  Interview: "#E8935B",
  Offer: "#9B8AFB",
  Rejected: "#EC7A5E"
};

export default function CareerFlowCopilot() {
  // Authentication & session state
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [usernameInput, setUsernameInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  
  // Navigation & panels
  const [activeTab, setActiveTab] = useState<"dashboard" | "discovery" | "tracker" | "resume" | "outreach" | "settings">("dashboard");
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Settings
  const [geminiKey, setGeminiKey] = useState("");
  const [hunterKey, setHunterKey] = useState("");
  const [senderEmail, setSenderEmail] = useState("");
  const [senderPassword, setSenderPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Job Aggregator & Cache Search
  const [jobs, setJobs] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [locationQuery, setLocationQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");
  const [syncing, setSyncing] = useState(false);
  const [customGh, setCustomGh] = useState("");
  const [customLv, setCustomLv] = useState("");

  // Kanban Tracker grouped stages applications
  const [trackerApps, setTrackerApps] = useState<Record<string, any[]>>({
    discovered: [],
    saved: [],
    applied: [],
    interview: [],
    offer: [],
    rejected: []
  });

  // AI Fit Score cache
  const [matchAnalysis, setMatchAnalysis] = useState<Record<string, any>>({});
  const [matchingJobId, setMatchingJobId] = useState<string | null>(null);

  // Resume Upload & Profile form editor
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [profileForm, setProfileForm] = useState<any>({
    name: "",
    email: "",
    phone: "",
    location: "",
    linkedin: "",
    github: "",
    portfolio: "",
    skills: "",
    summary: "",
    college: "",
    cgpa: "0.0",
    branch: "",
    grad_year: "2024",
    experience_level: "fresher"
  });

  // Playwright Automation triggers
  const [automationLogs, setAutomationLogs] = useState<Record<string, string>>({});
  const [playwrightMode, setPlaywrightMode] = useState<"Pre-Fill" | "Auto Apply">("Pre-Fill");

  // Recruiter Search & Outreach
  const [targetCompany, setTargetCompany] = useState("");
  const [searchingRecruiters, setSearchingRecruiters] = useState(false);
  const [recruiterLeads, setRecruiterLeads] = useState<any[]>([]);
  const [selectedLeadIdx, setSelectedLeadIdx] = useState<number | null>(null);
  const [draftSubject, setDraftSubject] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftingEmail, setDraftingEmail] = useState(false);

  // Load session from localStorage on start
  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    if (savedToken) {
      setToken(savedToken);
      fetchUserProfile(savedToken);
    }
  }, []);

  // Flash alerts timer
  useEffect(() => {
    if (successMsg) {
      const t = setTimeout(() => setSuccessMsg(""), 4000);
      return () => clearTimeout(t);
    }
  }, [successMsg]);

  useEffect(() => {
    if (errorMsg) {
      const t = setTimeout(() => setErrorMsg(""), 5000);
      return () => clearTimeout(t);
    }
  }, [errorMsg]);

  useEffect(() => {
    if (user) {
      if (user.has_gemini_key) setGeminiKey("••••••••••••••••");
      if (user.has_hunter_key) setHunterKey("••••••••••••••••");
      if (user.has_smtp_key) setSenderPassword("••••••••••••••••");
    }
  }, [user]);


  const fetchUserProfile = async (authToken: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
        setSenderEmail(data.email || "");
        
        if (data.has_gemini_key) setGeminiKey("••••••••••••••••");
        if (data.has_hunter_key) setHunterKey("••••••••••••••••");
        if (data.has_smtp_key) setSenderPassword("••••••••••••••••");
        
        if (data.resume_profile) {
          const prof = data.resume_profile;
          setProfileForm({
            name: prof.name || "",
            email: prof.email || "",
            phone: prof.phone || "",
            location: prof.location || "",
            linkedin: prof.linkedin || "",
            github: prof.github || "",
            portfolio: prof.portfolio || "",
            skills: Array.isArray(prof.skills) ? prof.skills.join(", ") : "",
            summary: prof.summary || "",
            college: prof.college || "",
            cgpa: String(prof.cgpa || "0.0"),
            branch: prof.branch || "",
            grad_year: String(prof.grad_year || "2024"),
            experience_level: prof.experience_level || "fresher"
          });
        }
        
        loadJobs(authToken);
        loadApplications(authToken);
      } else {
        logout();
      }
    } catch (e) {
      setErrorMsg("Failed to communicate with the backend microservice.");
    }
  };

  const loadJobs = async (authToken: string, q = "", loc = "", src = "All") => {
    try {
      const params = new URLSearchParams();
      if (q) params.append("q", q);
      if (loc) params.append("location", loc);
      if (src && src !== "All") params.append("source", src);
      
      const res = await fetch(`${API_BASE}/jobs/?${params.toString()}`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch (e) {
      console.error("Job fetching error", e);
    }
  };

  const loadApplications = async (authToken: string) => {
    try {
      const res = await fetch(`${API_BASE}/applications`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setTrackerApps(data);
      }
    } catch (e) {
      console.error("Applications loading error", e);
    }
  };

  const handleAuth = async (e?: React.FormEvent, customEmail?: string) => {
    if (e) e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    setSuccessMsg("");
    
    const targetEmail = (customEmail || emailInput || "candidate@joblantern.ai").trim().toLowerCase();
    const targetPass = passwordInput || "password";

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: targetEmail, password: targetPass })
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        setToken(data.access_token);
        await fetchUserProfile(data.access_token);
        setSuccessMsg(`Welcome to JobLantern, ${data.email}!`);
      } else {
        setErrorMsg(data.detail || "Login failed.");
      }
    } catch (err) {
      setErrorMsg("Unable to connect to JobLantern backend server.");
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setJobs([]);
    setTrackerApps({
      discovered: [],
      saved: [],
      applied: [],
      interview: [],
      offer: [],
      rejected: []
    });
    setActiveTab("dashboard");
  };

  const triggerSync = async () => {
    if (!token) return;
    setSyncing(true);
    setSuccessMsg("Triggering sync engine on backend...");
    try {
      const params = new URLSearchParams();
      if (customGh) params.append("custom_gh_boards", customGh);
      if (customLv) params.append("custom_lv_boards", customLv);
      
      const res = await fetch(`${API_BASE}/jobs/sync?${params.toString()}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setSuccessMsg("Scraper sync triggered. Refreshing cache...");
        setTimeout(() => {
          loadJobs(token, searchQuery, locationQuery, activeFilter);
          loadApplications(token);
        }, 3000);
      }
    } catch (e) {
      setErrorMsg("Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  const calculateFitScore = async (jobId: string) => {
    if (!token) return;
    setMatchingJobId(jobId);
    try {
      const jobObj = jobs.find(j => j.id === jobId);
      let url = `${API_BASE}/jobs/${jobId}/match`;
      if (jobId.startsWith("live-") && jobObj) {
        const params = new URLSearchParams({
          title: jobObj.title,
          company: jobObj.company,
          description: jobObj.description || ""
        });
        url += `?${params.toString()}`;
      }
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        setMatchAnalysis(prev => ({ ...prev, [jobId]: data }));
        setSuccessMsg("AI Score calculated!");
      } else {
        setErrorMsg(data.detail || "Fit score computation failed.");
      }
    } catch (e) {
      setErrorMsg("Scoring timed out.");
    } finally {
      setMatchingJobId(null);
    }
  };

  const saveUnsaveJob = async (jobId: string) => {
    if (!token) return;
    try {
      const jobObj = jobs.find(j => j.id === jobId);
      const isLive = jobId.startsWith("live-");
      
      const res = await fetch(`${API_BASE}/jobs/${jobId}/save`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}` 
        },
        body: isLive && jobObj ? JSON.stringify({
          title: jobObj.title,
          company: jobObj.company,
          url: jobObj.url,
          location: jobObj.location,
          description: jobObj.description,
          source: jobObj.source
        }) : undefined
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(data.message);
        loadJobs(token, searchQuery, locationQuery, activeFilter);
        loadApplications(token);
      }
    } catch (e) {
      setErrorMsg("Toggle save failed.");
    }
  };

  const updateApplicationStage = async (appId: string, targetStage: string) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/applications/${appId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ status: targetStage.toLowerCase() })
      });
      if (res.ok) {
        setSuccessMsg(`Moved application to ${targetStage}`);
        loadApplications(token);
        loadJobs(token, searchQuery, locationQuery, activeFilter);
      }
    } catch (e) {
      setErrorMsg("Failed to move stage.");
    }
  };

  const runPlaywrightBot = async (jobId: string, jobUrl: string) => {
    if (!token) return;
    setAutomationLogs(prev => ({ ...prev, [jobId]: "Spawning Playwright form automation..." }));
    try {
      const res = await fetch(`${API_BASE}/automation/apply`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          job_id: jobId,
          job_url: jobUrl,
          mode: playwrightMode,
          headless: playwrightMode === "Auto Apply"
        })
      });
      const data = await res.json();
      if (res.ok) {
        setAutomationLogs(prev => ({ ...prev, [jobId]: "Playwright pre-filled application!" }));
        setSuccessMsg("Pre-fill complete.");
        loadApplications(token);
      } else {
        setAutomationLogs(prev => ({ ...prev, [jobId]: `Failed: ${data.detail}` }));
      }
    } catch (e) {
      setAutomationLogs(prev => ({ ...prev, [jobId]: "Automation execution error." }));
    }
  };

  const handleResumeUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !uploadFile) return;
    setLoading(true);
    
    const formData = new FormData();
    formData.append("file", uploadFile);
    
    try {
      const res = await fetch(`${API_BASE}/resume`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg("Resume uploaded and parsed via Gemini!");
        fetchUserProfile(token);
      } else {
        setErrorMsg(data.detail || "Resume upload parse failed.");
      }
    } catch (e) {
      setErrorMsg("Resume processing error.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setLoading(true);
    try {
      const skillsArr = profileForm.skills.split(",").map((s: string) => s.trim());
      const res = await fetch(`${API_BASE}/resume`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          ...profileForm,
          cgpa: parseFloat(profileForm.cgpa),
          grad_year: parseInt(profileForm.grad_year),
          skills: skillsArr
        })
      });
      if (res.ok) {
        setSuccessMsg("Profile review edits saved!");
        fetchUserProfile(token);
      }
    } catch (e) {
      setErrorMsg("Failed to update profile.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfigs = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          gemini_api_key: geminiKey,
          hunter_api_key: hunterKey,
          sender_email: senderEmail,
          sender_app_password: senderPassword
        })
      });
      if (res.ok) {
        setSuccessMsg("Keys encrypted and stored successfully!");
        fetchUserProfile(token);
      }
    } catch (e) {
      setErrorMsg("Config update error.");
    } finally {
      setLoading(false);
    }
  };

  const handleSearchRecruiters = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setSearchingRecruiters(true);
    setRecruiterLeads([]);
    setSelectedLeadIdx(null);
    try {
      const res = await fetch(`${API_BASE}/outreach/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ company: targetCompany })
      });
      const data = await res.json();
      if (res.ok) {
        setRecruiterLeads(data);
        setSuccessMsg(`Resolved ${data.length} recruiter listings!`);
      }
    } catch (e) {
      setErrorMsg("Search error.");
    } finally {
      setSearchingRecruiters(false);
    }
  };

  const buildOutreachDraft = async (idx: number, lead: any) => {
    if (!token) return;
    setSelectedLeadIdx(idx);
    setDraftingEmail(true);
    setDraftSubject("");
    setDraftBody("");
    try {
      const res = await fetch(`${API_BASE}/outreach/draft`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          recruiter_name: lead.name,
          recruiter_title: lead.title,
          company: lead.company
        })
      });
      const data = await res.json();
      if (res.ok) {
        setDraftSubject(data.subject);
        setDraftBody(data.body);
      }
    } catch (e) {
      setErrorMsg("Drafting failed.");
    } finally {
      setDraftingEmail(false);
    }
  };

  const sendOutreachEmail = async (lead: any) => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/outreach/send`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          recipient_email: lead.email,
          subject: draftSubject,
          body: draftBody
        })
      });
      if (res.ok) {
        setSuccessMsg("Outreach email sent successfully via SMTP.");
        setSelectedLeadIdx(null);
      } else {
        setErrorMsg("Email delivery failed.");
      }
    } catch (e) {
      setErrorMsg("SMTP delivery timed out.");
    } finally {
      setLoading(false);
    }
  };

  // Login view
  if (!token) {
    return (
      <div className="min-h-screen bg-[#0A0F0D] flex flex-col justify-center items-center px-4 relative overflow-hidden font-sans">
        <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-[rgba(76,143,240,0.12)] blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-[rgba(240,176,87,0.12)] blur-[120px] pointer-events-none" />
        
        <div className="w-full max-w-md bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-2xl p-8 backdrop-blur-xl shadow-2xl relative">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-display font-semibold tracking-tight text-[#EDEFEA] flex justify-center items-center gap-2">
              <span className="brand-dot w-2.5 h-2.5 rounded-full bg-[#F0B057] shadow-[0_0_12px_#F0B057]" />
              JobLantern
            </h1>
            <p className="text-[#9BA8A1] mt-2 text-xs font-sans tracking-wide leading-relaxed">
              Lighting your path through a dark & confusing job search process — for candidates who feel confused where to apply.
            </p>
          </div>

          {errorMsg && (
            <div className="bg-red-950/30 border border-red-800/40 rounded-xl p-3 mb-6 flex items-start gap-2 text-red-400 text-xs">
              <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-xl p-3 mb-6 flex items-start gap-2 text-emerald-400 text-xs">
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          <form onSubmit={handleAuth} className="space-y-4">
            <div>
              <label className="block text-[#9BA8A1] text-[10px] font-mono uppercase tracking-wider mb-2">
                Email Address
              </label>
              <input
                type="email"
                required
                className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-xl px-4 py-3 text-[#EDEFEA] focus:outline-none focus:border-[#F0B057] text-xs transition"
                placeholder="candidate@joblantern.ai"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-[#9BA8A1] text-[10px] font-mono uppercase tracking-wider mb-2">
                Password
              </label>
              <input
                type="password"
                required
                className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-xl px-4 py-3 text-[#EDEFEA] focus:outline-none focus:border-[#F0B057] text-xs transition"
                placeholder="Enter your password"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#F0B057] hover:bg-[#e09e47] text-[#241705] font-semibold py-3 rounded-xl transition duration-300 shadow-lg text-xs flex justify-center items-center gap-2 cursor-pointer mt-4"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Sign In to JobLantern
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[rgba(255,255,255,0.08)]" /></div>
            <div className="relative flex justify-center text-[10px] uppercase font-mono"><span className="bg-[#0D1210] px-2 text-[#5C6A63]">Or Quick Access</span></div>
          </div>

          <button
            onClick={() => handleAuth(undefined, "candidate@joblantern.ai")}
            disabled={loading}
            className="w-full bg-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.08)] border border-[rgba(255,255,255,0.1)] text-[#EDEFEA] font-semibold py-3 rounded-xl transition text-xs flex justify-center items-center gap-2 cursor-pointer"
          >
            1-Click Demo Login (Instant Access)
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0F0D] text-[#EDEFEA] flex relative font-sans">
      <div className="absolute top-[-10%] left-[-10%] w-[45vw] h-[45vw] rounded-full bg-[rgba(76,143,240,0.08)] blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[45vw] h-[45vw] rounded-full bg-[rgba(240,176,87,0.06)] blur-[120px] pointer-events-none z-0" />

      {/* Sidebar Navigation */}
      <aside className="w-56 bg-[rgba(255,255,255,0.015)] border-r border-[rgba(255,255,255,0.08)] backdrop-blur-xl flex flex-col justify-between shrink-0 relative z-20 font-sans select-none">
        <div>
          <div className="p-5 border-b border-[rgba(255,255,255,0.08)]">
            <h2 className="text-sm font-display font-bold text-[#EDEFEA] flex items-center gap-1.5 font-serif italic">
              <span className="w-1.5 h-1.5 rounded-full bg-[#F0B057] shadow-[0_0_6px_rgba(240,176,87,0.8)]" />
              JobLantern
            </h2>
            <div className="text-[#5C6A63] text-[9px] mt-1 font-mono truncate">{user?.email}</div>
          </div>

          <nav className="p-3 space-y-1">
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition font-medium ${
                activeTab === "dashboard" ? "bg-[rgba(255,255,255,0.07)] text-[#EDEFEA] border border-[rgba(255,255,255,0.09)]" : "text-[#9BA8A1] hover:bg-[rgba(255,255,255,0.035)] hover:text-[#EDEFEA]"
              }`}
            >
              <BarChart2 className="w-4 h-4 text-[#F0B057]" />
              <span>Dashboard</span>
            </button>

            <button
              onClick={() => setActiveTab("discovery")}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition font-medium ${
                activeTab === "discovery" ? "bg-[rgba(255,255,255,0.07)] text-[#EDEFEA] border border-[rgba(255,255,255,0.09)]" : "text-[#9BA8A1] hover:bg-[rgba(255,255,255,0.035)] hover:text-[#EDEFEA]"
              }`}
            >
              <Briefcase className="w-4 h-4 text-[#F0B057]" />
              <span>Discovery Hub</span>
            </button>

            <button
              onClick={() => setActiveTab("tracker")}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition font-medium ${
                activeTab === "tracker" ? "bg-[rgba(255,255,255,0.07)] text-[#EDEFEA] border border-[rgba(255,255,255,0.09)]" : "text-[#9BA8A1] hover:bg-[rgba(255,255,255,0.035)] hover:text-[#EDEFEA]"
              }`}
            >
              <CheckCircle2 className="w-4 h-4 text-[#F0B057]" />
              <span>Pipeline Tracker</span>
            </button>

            <button
              onClick={() => setActiveTab("resume")}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition font-medium ${
                activeTab === "resume" ? "bg-[rgba(255,255,255,0.07)] text-[#EDEFEA] border border-[rgba(255,255,255,0.09)]" : "text-[#9BA8A1] hover:bg-[rgba(255,255,255,0.035)] hover:text-[#EDEFEA]"
              }`}
            >
              <FileText className="w-4 h-4 text-[#F0B057]" />
              <span>Resume & Profile</span>
            </button>

            <button
              onClick={() => setActiveTab("outreach")}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition font-medium ${
                activeTab === "outreach" ? "bg-[rgba(255,255,255,0.07)] text-[#EDEFEA] border border-[rgba(255,255,255,0.09)]" : "text-[#9BA8A1] hover:bg-[rgba(255,255,255,0.035)] hover:text-[#EDEFEA]"
              }`}
            >
              <Mail className="w-4 h-4 text-[#F0B057]" />
              <span>Outreach Mailer</span>
            </button>

            <button
              onClick={() => setActiveTab("settings")}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition font-medium ${
                activeTab === "settings" ? "bg-[rgba(255,255,255,0.07)] text-[#EDEFEA] border border-[rgba(255,255,255,0.09)]" : "text-[#9BA8A1] hover:bg-[rgba(255,255,255,0.035)] hover:text-[#EDEFEA]"
              }`}
            >
              <Settings className="w-4 h-4 text-[#F0B057]" />
              <span>Settings / Keys</span>
            </button>
          </nav>
        </div>

        <div className="p-3 border-t border-[rgba(255,255,255,0.08)]">
          <button
            onClick={logout}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#9BA8A1] hover:bg-red-950/20 hover:text-red-400 transition"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Close Session</span>
          </button>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 overflow-y-auto p-8 relative z-10 font-sans">
        {/* Flash alerts */}
        {successMsg && (
          <div className="fixed bottom-6 right-6 bg-[#0A0F0D] border border-[#F0B057] text-[#EDEFEA] rounded-2xl p-4 shadow-2xl z-50 flex items-center gap-3 max-w-sm animate-slide-in">
            <CheckCircle2 className="w-5 h-5 text-[#F0B057] shrink-0" />
            <div className="text-xs font-semibold">{successMsg}</div>
          </div>
        )}

        {errorMsg && (
          <div className="fixed bottom-6 right-6 bg-[#0A0F0D] border border-[#EC7A5E] text-[#EDEFEA] rounded-2xl p-4 shadow-2xl z-50 flex items-center gap-3 max-w-sm animate-slide-in">
            <ShieldAlert className="w-5 h-5 text-[#EC7A5E] shrink-0" />
            <div className="text-xs font-semibold">{errorMsg}</div>
          </div>
        )}

        {/* --- TAB 1: DASHBOARD --- */}
        {activeTab === "dashboard" && (
          <div className="space-y-8 animate-fade-in">
            {/* Inspirational Hero Lantern Section */}
            <div className="relative overflow-hidden bg-gradient-to-br from-[rgba(240,176,87,0.12)] via-[rgba(76,143,240,0.06)] to-[rgba(255,255,255,0.02)] border border-[rgba(240,176,87,0.25)] rounded-3xl p-8 backdrop-blur-xl shadow-2xl">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#F0B057] flex items-center gap-2 bg-[rgba(240,176,87,0.1)] px-3 py-1.5 rounded-full border border-[rgba(240,176,87,0.2)]">
                  <span className="w-2 h-2 bg-[#F0B057] rounded-full animate-ping" />
                  AI Engine Active • Zero-Config Default Groq Key Built-In
                </div>

                <div className="text-[10px] font-mono text-[#9BA8A1] bg-[rgba(255,255,255,0.04)] px-3 py-1.5 rounded-full border border-[rgba(255,255,255,0.08)]">
                  JobLantern v3.0 • Light Your Career Path
                </div>
              </div>

              {/* Inspiring Animated Quotes Carousel */}
              <div className="my-4 space-y-3">
                <h1 className="text-3xl md:text-4xl font-serif italic font-semibold text-[#EDEFEA] leading-tight tracking-tight">
                  "Lighting your path through a dark & confusing job search."
                </h1>
                <p className="text-sm text-[#9BA8A1] max-w-2xl leading-relaxed italic">
                  "In an overcrowded market, JobLantern illuminates the exact opportunities tailored for your unique skills. Every application brings you one step closer to your breakthrough."
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
                <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-2xl p-4">
                  <div className="text-[#F0B057] font-mono text-2xl font-bold">{jobs.length}</div>
                  <div className="text-[10px] text-[#9BA8A1] mt-1 font-semibold uppercase">Scanned Postings</div>
                </div>
                <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-2xl p-4">
                  <div className="text-[#4C8FF0] font-mono text-2xl font-bold">{user?.has_resume ? "Ready" : "Uploaded"}</div>
                  <div className="text-[10px] text-[#9BA8A1] mt-1 font-semibold uppercase">Resume Parsed</div>
                </div>
                <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-2xl p-4">
                  <div className="text-emerald-400 font-mono text-2xl font-bold">Groq AI</div>
                  <div className="text-[10px] text-[#9BA8A1] mt-1 font-semibold uppercase">Default Engine</div>
                </div>
                <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-2xl p-4">
                  <div className="text-[#EDEFEA] font-mono text-2xl font-bold">Live</div>
                  <div className="text-[10px] text-[#9BA8A1] mt-1 font-semibold uppercase">LinkedIn & Naukri</div>
                </div>
              </div>
            </div>

            {/* Sync control */}
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-2xl p-6 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#9BA8A1]">Connector Orchestrator Control</h3>
              <p className="text-xs text-[#5C6A63] leading-relaxed">
                Manually trigger background job synchronizers across LinkedIn, Naukri, Glassdoor, Greenhouse, and Lever pipelines.
              </p>
              <div className="flex gap-4">
                <button
                  onClick={triggerSync}
                  disabled={syncing}
                  className="bg-[#F0B057] hover:bg-[#e09e47] disabled:bg-[#d8a765] text-[#241705] px-5 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition cursor-pointer shadow-lg"
                >
                  {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  Scrape & Sync Jobs Now
                </button>
              </div>
            </div>
          </div>
        )}

        {/* --- TAB 2: DISCOVERY HUB --- */}
        {activeTab === "discovery" && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h2 className="text-2xl font-serif text-[#EDEFEA]">Discovery Hub</h2>
              <p className="text-[#9BA8A1] text-xs mt-1">Queries the normalized database cache and computes compatibility score.</p>
            </div>

            {/* Custom Watchlist boards */}
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.07)] rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[#9BA8A1] text-[10px] font-semibold mb-2">Custom Greenhouse boards</label>
                <input
                  type="text"
                  placeholder="e.g. stripe, flexport"
                  className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                  value={customGh}
                  onChange={(e) => setCustomGh(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-[#9BA8A1] text-[10px] font-semibold mb-2">Custom Lever boards</label>
                <input
                  type="text"
                  placeholder="e.g. figma, posthog"
                  className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                  value={customLv}
                  onChange={(e) => setCustomLv(e.target.value)}
                />
              </div>
            </div>

            {/* Filters Row */}
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div>
                <label className="block text-[#9BA8A1] text-[10px] font-mono uppercase tracking-wider mb-2">Role Keywords</label>
                <input
                  type="text"
                  placeholder="e.g. Developer, Python"
                  className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2.5 text-[#EDEFEA] focus:outline-none text-xs"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-[#9BA8A1] text-[10px] font-mono uppercase tracking-wider mb-2">Location</label>
                <input
                  type="text"
                  placeholder="e.g. Remote, Chennai"
                  className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2.5 text-[#EDEFEA] focus:outline-none text-xs"
                  value={locationQuery}
                  onChange={(e) => setLocationQuery(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-[#9BA8A1] text-[10px] font-mono uppercase tracking-wider mb-2">Source Feed</label>
                <select
                  className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2.5 text-[#EDEFEA] focus:outline-none text-xs cursor-pointer"
                  value={activeFilter}
                  onChange={(e) => setActiveFilter(e.target.value)}
                >
                  <option value="All">All Board Feeds</option>
                  <option value="Greenhouse">Greenhouse</option>
                  <option value="Lever">Lever</option>
                  <option value="Ashby">Ashby</option>
                  <option value="RemoteOK">RemoteOK</option>
                  <option value="Remotive">Remotive</option>
                  <option value="Arbeitnow">Arbeitnow</option>
                  <option value="LinkedIn">LinkedIn (Live Search)</option>
                  <option value="Naukri">Naukri (Live Search)</option>
                  <option value="Glassdoor">Glassdoor (Live Search)</option>
                </select>
              </div>

              <button
                onClick={() => loadJobs(token!, searchQuery, locationQuery, activeFilter)}
                className="bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.09)] text-[#EDEFEA] font-semibold py-2.5 rounded-lg text-xs transition flex justify-center items-center gap-1.5 cursor-pointer animate-pulse"
              >
                <Search className="w-3.5 h-3.5" />
                Query Database
              </button>
            </div>

            {/* Automation parameters */}
            <div className="flex gap-6 text-xs px-1 text-[#9BA8A1] select-none">
              <span>Playwright pre-fill mode:</span>
              <label className="flex items-center gap-2 cursor-pointer text-[#EDEFEA]">
                <input
                  type="radio"
                  name="playMode"
                  checked={playwrightMode === "Pre-Fill"}
                  onChange={() => setPlaywrightMode("Pre-Fill")}
                  className="accent-[#F0B057]"
                />
                <span>Visible Pre-Fill</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-[#EDEFEA]">
                <input
                  type="radio"
                  name="playMode"
                  checked={playwrightMode === "Auto Apply"}
                  onChange={() => setPlaywrightMode("Auto Apply")}
                  className="accent-[#F0B057]"
                />
                <span>Silent Auto-apply (headless)</span>
              </label>
            </div>

            {/* Job cards list */}
            <div className="space-y-4">
              {jobs.length === 0 ? (
                <div className="bg-[rgba(255,255,255,0.01)] border border-[rgba(255,255,255,0.06)] rounded-2xl p-12 text-center text-[#5C6A63] text-xs">
                  No active cached listings matching parameters. Run sync above.
                </div>
              ) : (
                jobs.map((job) => {
                  const isScrapable = ["Greenhouse", "Lever"].includes(job.source);
                  const analysis = matchAnalysis[job.id];
                  
                  return (
                    <div key={job.id} className="bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.08)] rounded-xl overflow-hidden flex transition duration-150 hover:bg-[rgba(255,255,255,0.04)] hover:border-[rgba(255,255,255,0.15)] relative">
                      {/* Left Momentum Rail Stage Indicator */}
                      <div 
                        className="w-1 absolute left-0 top-0 bottom-0 shrink-0" 
                        style={{ backgroundColor: STAGE_COLORS[job.stage || "Discovered"] }} 
                      />
                      
                      <div className="flex-1 p-5 pl-6 space-y-4">
                        <div className="flex justify-between items-start flex-wrap gap-4">
                          <div>
                            <h4 className="text-sm font-semibold text-[#EDEFEA]">{job.title}</h4>
                            <div className="text-xs text-[#9BA8A1] mt-0.5 font-medium">
                              {job.company} — {job.location || "Location Offline"}
                            </div>
                            <div className="text-[10px] text-[#5C6A63] mt-2 font-mono uppercase">
                              via {job.source.toLowerCase()} • {job.posted_date || "recently"}
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="font-mono text-xs text-[#EDEFEA] bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] px-2.5 py-1 rounded-md">
                              {job.salary}
                            </span>
                            
                            {/* Match ring loader SVG */}
                            <div className="flex flex-col items-center gap-1 shrink-0">
                              <div className="relative w-10 h-10 select-none">
                                <svg width="40" height="40" className="transform -rotate-90">
                                  <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                                  <circle 
                                    cx="20" 
                                    cy="20" 
                                    r="16" 
                                    fill="none" 
                                    stroke="#F0B057" 
                                    strokeWidth="3" 
                                    strokeDasharray="100" 
                                    strokeDashoffset={analysis ? 100 - analysis.score : 100}
                                    className="transition-all duration-1000 ease-out" 
                                  />
                                </svg>
                                <div className="absolute inset-0 flex items-center justify-center font-mono text-[10px] font-bold text-[#EDEFEA]">
                                  {analysis ? `${analysis.score}` : "—"}
                                </div>
                              </div>
                              <span className="text-[8px] font-mono text-[#5C6A63] uppercase">match</span>
                            </div>
                          </div>
                        </div>

                        {/* Collapsible Details */}
                        <details className="text-xs text-[#9BA8A1] cursor-pointer">
                          <summary className="font-semibold text-[#F0B057] hover:underline list-none flex items-center gap-1 select-none">
                            <ChevronRight className="w-3.5 h-3.5" /> Description & details
                          </summary>
                          <div className="mt-3 p-4 bg-[#0A0F0D] border border-[rgba(255,255,255,0.04)] rounded-lg text-xs leading-relaxed whitespace-pre-wrap max-h-56 overflow-y-auto font-sans text-[#9BA8A1]">
                            {job.description}
                          </div>
                        </details>

                        {/* Fit Scoring Analysis Panel */}
                        {analysis && (
                          <div className="bg-[rgba(240,176,87,0.03)] border border-[rgba(240,176,87,0.1)] rounded-lg p-4 text-xs space-y-3 font-sans">
                            <div className="leading-relaxed">
                              <span className="font-bold text-[#EDEFEA] block mb-1">AI Match Summary:</span>
                              <span className="text-[#9BA8A1]">{analysis.summary}</span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <div className="font-bold text-[#4C8FF0] mb-1.5 flex items-center gap-1">✓ Matched Keywords</div>
                                <div className="flex flex-wrap gap-1">
                                  {analysis.matched_skills.map((s: string) => (
                                    <span key={s} className="bg-[rgba(76,143,240,0.08)] border border-[rgba(76,143,240,0.15)] text-[#4C8FF0] px-2 py-0.5 rounded font-mono text-[9px]">{s}</span>
                                  ))}
                                </div>
                              </div>

                              <div>
                                <div className="font-bold text-[#EC7A5E] mb-1.5 flex items-center gap-1">✗ Missing Keywords</div>
                                <div className="flex flex-wrap gap-1">
                                  {analysis.missing_skills.map((s: string) => (
                                    <span key={s} className="bg-transparent border border-dashed border-[rgba(236,122,94,0.3)] text-[#EC7A5E] px-2 py-0.5 rounded font-mono text-[9px]">{s}</span>
                                  ))}
                                </div>
                              </div>
                            </div>

                            <div>
                              <div className="font-bold text-[#EDEFEA] mb-1.5">ATS Optimization Instructions</div>
                              <ul className="list-disc list-inside space-y-1 text-[#9BA8A1]">
                                {analysis.actionable_tips.map((t: string, i: number) => (
                                  <li key={i}>{t}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}

                        {/* Action buttons */}
                        <div className="flex items-center gap-3 flex-wrap">
                          <button
                            onClick={() => calculateFitScore(job.id)}
                            disabled={matchingJobId === job.id}
                            className="bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.06)] text-[#EDEFEA] font-semibold px-3 py-2 rounded-lg text-xs transition flex items-center gap-1.5 cursor-pointer"
                          >
                            {matchingJobId === job.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BarChart2 className="w-3.5 h-3.5" />}
                            Calculate Fit Score
                          </button>

                          <button
                            onClick={() => saveUnsaveJob(job.id)}
                            className="bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.06)] text-[#EDEFEA] font-semibold px-3 py-2 rounded-lg text-xs transition flex items-center gap-1.5 cursor-pointer"
                          >
                            {job.stage === "Saved" ? "Unsave Job" : "Save to Tracker"}
                          </button>

                          <button
                            onClick={() => runPlaywrightBot(job.id, job.url)}
                            className="bg-[#F0B057] hover:bg-[#e09e47] text-[#241705] font-semibold px-3 py-2 rounded-lg text-xs transition flex items-center gap-1.5 cursor-pointer shadow"
                          >
                            <Zap className="w-3.5 h-3.5" />
                            AI Auto-Fill (Playwright)
                          </button>

                          <a href={job.url} target="_blank" rel="noopener noreferrer">
                            <button className="bg-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.08)] border border-[rgba(255,255,255,0.08)] text-[#EDEFEA] px-3 py-2 rounded-lg text-xs transition flex items-center gap-1 cursor-pointer">
                              Apply Manually
                            </button>
                          </a>

                          {automationLogs[job.id] && (
                            <span className="text-[10px] text-[#F0B057] font-semibold animate-pulse block">
                              {automationLogs[job.id]}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* --- TAB 3: PIPELINE TRACKER --- */}
        {activeTab === "tracker" && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h2 className="text-2xl font-serif text-[#EDEFEA]">Pipeline Rail Tracker</h2>
              <p className="text-[#9BA8A1] text-xs mt-1">Grouped kanban view loaded directly from Supabase tables.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-6 gap-3 overflow-x-auto pb-4 select-none">
              {(["discovered", "saved", "applied", "interview", "offer", "rejected"] as const).map((stage) => {
                const stageList = trackerApps[stage] || [];
                
                return (
                  <div key={stage} className="bg-[rgba(255,255,255,0.015)] border border-[rgba(255,255,255,0.08)] rounded-xl p-3 min-w-[160px] flex flex-col space-y-3">
                    <div className="flex items-center gap-2 border-b border-[rgba(255,255,255,0.05)] pb-2">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: STAGE_COLORS[stage.charAt(0).toUpperCase() + stage.slice(1)] }} />
                      <span className="text-[11px] font-semibold text-[#EDEFEA] capitalize">{stage}</span>
                      <span className="ml-auto font-mono text-[10px] text-[#5C6A63]">{stageList.length}</span>
                    </div>

                    <div className="flex-1 space-y-2">
                      {stageList.length === 0 ? (
                        <div className="border border-dashed border-[rgba(255,255,255,0.05)] rounded-lg p-6 text-center text-[10px] text-[#5C6A63]">
                          Empty
                        </div>
                      ) : (
                        stageList.map((app) => (
                          <div key={app.id} className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.07)] rounded-lg p-3 hover:border-[rgba(255,255,255,0.15)] transition text-xs relative overflow-hidden">
                            <div className="w-0.5 absolute left-0 top-0 bottom-0" style={{ backgroundColor: STAGE_COLORS[stage.charAt(0).toUpperCase() + stage.slice(1)] }} />
                            <div className="font-semibold text-[#EDEFEA] truncate">{app.job?.title}</div>
                            <div className="text-[10px] text-[#9BA8A1] mt-0.5 truncate">{app.job?.company}</div>
                            
                            {/* Toggle buttons */}
                            <div className="flex gap-1 mt-2.5 border-t border-[rgba(255,255,255,0.04)] pt-2 overflow-x-auto">
                              {(["discovered", "saved", "applied", "interview", "offer", "rejected"] as const).map(next => {
                                if (next === stage) return null;
                                return (
                                  <button
                                    key={next}
                                    title={`Move to ${next}`}
                                    onClick={() => updateApplicationStage(app.id, next)}
                                    className="w-2 h-2 rounded-full hover:scale-125 transition shrink-0 cursor-pointer"
                                    style={{ backgroundColor: STAGE_COLORS[next.charAt(0).toUpperCase() + next.slice(1)] }}
                                  />
                                );
                              })}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* --- TAB 4: RESUME WORKSPACE --- */}
        {activeTab === "resume" && (
          <div className="space-y-6 animate-fade-in font-sans">
            <div>
              <h2 className="text-2xl font-serif text-[#EDEFEA]">Resume & Profile</h2>
              <p className="text-[#9BA8A1] text-xs mt-1">Manage structured JSON profile specifications parsed by Gemini.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-6">
                <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-6 space-y-4">
                  <h3 className="text-sm font-semibold text-[#EDEFEA]">Upload PDF Resume</h3>
                  
                  <form onSubmit={handleResumeUpload} className="space-y-4">
                    <div className="border border-dashed border-[rgba(255,255,255,0.08)] rounded-lg p-6 flex flex-col items-center justify-center bg-[#0A0F0D]">
                      <FileText className="w-8 h-8 text-[#F0B057] mb-2" />
                      <input
                        type="file"
                        accept=".pdf"
                        onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                        className="text-xs text-[#9BA8A1] file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[rgba(240,176,87,0.1)] file:text-[#F0B057] file:cursor-pointer"
                      />
                      <p className="text-[10px] text-[#5C6A63] mt-2">Only PDF files up to 5MB supported</p>
                    </div>

                    <button
                      type="submit"
                      disabled={loading || !uploadFile}
                      className="w-full bg-[#F0B057] hover:bg-[#e09e47] disabled:bg-[#d8a765] text-[#241705] font-semibold py-2.5 rounded-lg text-xs transition flex justify-center items-center gap-1.5 cursor-pointer"
                    >
                      {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      Upload and Parse
                    </button>
                  </form>

                  {user?.has_resume && (
                    <div className="mt-4 p-4 bg-[rgba(240,176,87,0.02)] border border-[rgba(240,176,87,0.1)] rounded-lg">
                      <div className="text-xs">
                        <div className="font-semibold text-[#EDEFEA]">Parsed Resume File:</div>
                        <div className="text-[#F0B057] mt-0.5 font-mono text-[11px] truncate">{user.resume_filename}</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Editable Profile form */}
              <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-6 space-y-4">
                <h3 className="text-sm font-semibold text-[#EDEFEA]">Edit Structured Profile</h3>
                
                <form onSubmit={handleSaveProfile} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Name</label>
                      <input
                        type="text"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.name}
                        onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                      />
                    </div>

                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Email</label>
                      <input
                        type="email"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.email}
                        onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Phone</label>
                      <input
                        type="text"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.phone}
                        onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                      />
                    </div>

                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Location</label>
                      <input
                        type="text"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.location}
                        onChange={(e) => setProfileForm({ ...profileForm, location: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">College</label>
                      <input
                        type="text"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.college}
                        onChange={(e) => setProfileForm({ ...profileForm, college: e.target.value })}
                      />
                    </div>

                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">CGPA</label>
                      <input
                        type="text"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.cgpa}
                        onChange={(e) => setProfileForm({ ...profileForm, cgpa: e.target.value })}
                      />
                    </div>

                    <div>
                      <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Grad Year</label>
                      <input
                        type="text"
                        className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                        value={profileForm.grad_year}
                        onChange={(e) => setProfileForm({ ...profileForm, grad_year: e.target.value })}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">LinkedIn Profile</label>
                    <input
                      type="text"
                      className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                      value={profileForm.linkedin}
                      onChange={(e) => setProfileForm({ ...profileForm, linkedin: e.target.value })}
                    />
                  </div>

                  <div>
                    <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Skills (comma separated)</label>
                    <textarea
                      rows={3}
                      className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs font-mono"
                      value={profileForm.skills}
                      onChange={(e) => setProfileForm({ ...profileForm, skills: e.target.value })}
                    />
                  </div>

                  <div>
                    <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1">Summary</label>
                    <textarea
                      rows={3}
                      className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                      value={profileForm.summary}
                      onChange={(e) => setProfileForm({ ...profileForm, summary: e.target.value })}
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full bg-[#F0B057] hover:bg-[#e09e47] text-[#241705] font-semibold py-2.5 rounded-lg text-xs transition cursor-pointer"
                  >
                    Save Profile Details
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* --- TAB 5: OUTREACH --- */}
        {activeTab === "outreach" && (
          <div className="space-y-6 animate-fade-in font-sans">
            <div>
              <h2 className="text-2xl font-serif text-[#EDEFEA]">Outreach Mailer</h2>
              <p className="text-[#9BA8A1] text-xs mt-1">Locate recruiters and send cold email campaigns securely.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-6 space-y-4 lg:col-span-1 h-fit">
                <h3 className="text-sm font-semibold text-[#EDEFEA]">Find Recruiter Contacts</h3>
                
                <form onSubmit={handleSearchRecruiters} className="space-y-4">
                  <div>
                    <label className="block text-[#9BA8A1] text-[10px] font-semibold mb-2">Target Company Name</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Stripe"
                      className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2.5 text-[#EDEFEA] focus:outline-none text-xs"
                      value={targetCompany}
                      onChange={(e) => setTargetCompany(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={searchingRecruiters}
                    className="w-full bg-[#F0B057] hover:bg-[#e09e47] text-[#241705] font-semibold py-2.5 rounded-lg text-xs transition flex justify-center items-center gap-1.5 cursor-pointer"
                  >
                    {searchingRecruiters && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Scan Recruiter Contacts
                  </button>
                </form>
              </div>

              <div className="lg:col-span-2 space-y-6">
                {recruiterLeads.length > 0 && (
                  <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-6 space-y-4">
                    <h3 className="text-sm font-semibold text-[#EDEFEA]">Resolved Corporate Contacts</h3>
                    
                    <div className="space-y-3.5">
                      {recruiterLeads.map((lead, idx) => (
                        <div key={idx} className="bg-[#0A0F0D] border border-[rgba(255,255,255,0.06)] rounded-xl p-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 text-xs">
                          <div>
                            <div className="font-bold text-[#EDEFEA] text-sm">{lead.name}</div>
                            <div className="text-[#9BA8A1] mt-0.5">{lead.title} at <b>{lead.company}</b></div>
                            <div className="text-[11px] mt-2 flex items-center gap-2">
                              Email: <code className="bg-[rgba(255,255,255,0.03)] px-1.5 py-0.5 rounded border border-[rgba(255,255,255,0.08)] text-[#EDEFEA] font-mono">{lead.email}</code> 
                              <span className="bg-emerald-950/40 border border-emerald-900/40 text-emerald-400 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase">
                                {lead.method}
                              </span>
                            </div>
                          </div>

                          <div className="flex gap-2 shrink-0">
                            <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer">
                              <button className="bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.06)] text-[#EDEFEA] px-3 py-1.5 rounded-lg transition font-medium">
                                Profile
                              </button>
                            </a>
                            <button
                              onClick={() => buildOutreachDraft(idx, lead)}
                              className="bg-[#F0B057] hover:bg-[#e09e47] text-[#241705] px-3 py-1.5 rounded-lg font-medium transition cursor-pointer"
                            >
                              Draft Outreach
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedLeadIdx !== null && (
                  <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-6 space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-sm font-semibold text-[#EDEFEA]">Outreach Email Draft</h3>
                      <button onClick={() => setSelectedLeadIdx(null)} className="text-xs text-[#5C6A63] hover:underline">Discard Draft</button>
                    </div>

                    <div className="space-y-4">
                      {draftingEmail ? (
                        <div className="py-12 flex flex-col justify-center items-center gap-3 text-[#5C6A63] text-xs">
                          <Loader2 className="w-6 h-6 animate-spin text-[#F0B057]" />
                          <span>AI is customizing cold email outreach...</span>
                        </div>
                      ) : (
                        <>
                          <div>
                            <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1.5">Recipient Email</label>
                            <input
                              type="text"
                              className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs font-mono"
                              value={recruiterLeads[selectedLeadIdx]?.email}
                              onChange={(e) => {
                                const copy = [...recruiterLeads];
                                copy[selectedLeadIdx].email = e.target.value;
                                setRecruiterLeads(copy);
                              }}
                            />
                          </div>

                          <div>
                            <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1.5">Subject</label>
                            <input
                              type="text"
                              className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs"
                              value={draftSubject}
                              onChange={(e) => setDraftSubject(e.target.value)}
                            />
                          </div>

                          <div>
                            <label className="block text-[#9BA8A1] text-[9px] font-mono uppercase tracking-wider mb-1.5">Email Body</label>
                            <textarea
                              rows={10}
                              className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-md px-3 py-2 text-[#EDEFEA] focus:outline-none text-xs font-mono leading-relaxed"
                              value={draftBody}
                              onChange={(e) => setDraftBody(e.target.value)}
                            />
                          </div>

                          <button
                            onClick={() => sendOutreachEmail(recruiterLeads[selectedLeadIdx])}
                            disabled={loading}
                            className="bg-[#F0B057] hover:bg-[#e09e47] disabled:bg-[#d8a765] text-[#241705] font-semibold py-3 rounded-lg text-xs w-full transition flex justify-center items-center gap-2 cursor-pointer"
                          >
                            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                            <Send className="w-3.5 h-3.5" />
                            Deliver Cold Email Outreach
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* --- TAB 6: SETTINGS --- */}
        {activeTab === "settings" && (
          <div className="space-y-6 animate-fade-in font-sans">
            <div>
              <h2 className="text-2xl font-serif text-[#EDEFEA]">Key Configurations</h2>
              <p className="text-[#9BA8A1] text-xs mt-1">Configure secure credential parameter values.</p>
            </div>

            <div className="max-w-xl bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.08)] rounded-xl p-8 space-y-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-[#EDEFEA] text-xs font-semibold mb-2">Gemini API Key</label>
                  <input
                    type="password"
                    placeholder={user?.has_gemini_key ? "Key configured (••••••••••••••••)" : "Enter your Gemini Key"}
                    className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-4 py-2.5 text-[#EDEFEA] focus:outline-none text-xs"
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                  />
                  <div className="text-[#5C6A63] text-[10px] mt-1.5">Obtained from Google AI Studio. Used for parsing, cover letters, and outreach emails.</div>
                </div>

                <div>
                  <label className="block text-[#EDEFEA] text-xs font-semibold mb-2">Hunter.io API Key (Optional)</label>
                  <input
                    type="password"
                    placeholder={user?.has_hunter_key ? "Key configured (••••••••••••••••)" : "Enter your Hunter.io Key"}
                    className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-4 py-2.5 text-[#EDEFEA] focus:outline-none text-xs"
                    value={hunterKey}
                    onChange={(e) => setHunterKey(e.target.value)}
                  />
                  <div className="text-[#5C6A63] text-[10px] mt-1.5">Used for verifying business email structures. Standard guesser runs if empty.</div>
                </div>

                <div>
                  <label className="block text-[#EDEFEA] text-xs font-semibold mb-2">Gmail Address (SMTP Outreach)</label>
                  <input
                    type="email"
                    placeholder="you@gmail.com"
                    className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-4 py-2.5 text-[#EDEFEA] focus:outline-none text-xs"
                    value={senderEmail}
                    onChange={(e) => setSenderEmail(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-[#EDEFEA] text-xs font-semibold mb-2">Gmail App Password</label>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      placeholder={user?.has_smtp_key ? "Key configured (••••••••••••••••)" : "16-character App Password"}
                      className="w-full bg-[#0A0F0D] border border-[rgba(255,255,255,0.08)] rounded-lg px-4 py-2.5 text-[#EDEFEA] focus:outline-none text-xs pr-10"
                      value={senderPassword}
                      onChange={(e) => setSenderPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-3 text-slate-500 hover:text-slate-300 cursor-pointer"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <div className="text-[#5C6A63] text-[10px] mt-1.5">Must be generated inside your Google Account Settings under Security (App Passwords).</div>
                </div>
              </div>

              <button
                onClick={handleSaveConfigs}
                disabled={loading}
                className="w-full bg-[#F0B057] hover:bg-[#e09e47] disabled:bg-[#d8a765] text-[#241705] font-semibold py-3 rounded-lg text-xs transition flex justify-center items-center gap-2 cursor-pointer"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                Save and Encrypt Keys
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
