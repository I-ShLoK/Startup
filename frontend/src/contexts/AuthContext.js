import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
} from "react";
import { supabase } from "@/lib/supabase";
import axios from "axios";

/* =====================================================
   BACKEND CONFIG — TOP LEVEL ONLY (VERY IMPORTANT)
===================================================== */

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL ||
  process.env.REACT_APP_BACKEND_URL;

if (!BACKEND_URL) {
  throw new Error("❌ BACKEND URL NOT SET");
}

const API = `${BACKEND_URL}/api`;

const apiClient = axios.create({
  baseURL: API,
});

/* =====================================================
   AUTH CONTEXT
===================================================== */

const AuthContext = createContext({});
export const useAuth = () => useContext(AuthContext);

/* =====================================================
   ROLE / PERMISSIONS
===================================================== */

const PERMISSIONS = {
  canManageContent: (role) => ["founder", "manager"].includes(role),
  canViewAnalytics: (role) => ["founder", "manager"].includes(role),
  canAccessPitch: (role) => role === "founder",
  canManageTeam: (role) => role === "founder",
  canManageStartup: (role) => role === "founder",
};

/* =====================================================
   PROVIDER
===================================================== */

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  const [startups, setStartups] = useState([]);
  const [currentStartup, setCurrentStartup] = useState(null);
  const [startupsLoaded, setStartupsLoaded] = useState(false);

  /* -----------------------------
     AUTH HEADERS
  ----------------------------- */

  const getAuthHeaders = useCallback(
    () =>
      session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {},
    [session]
  );

  /* -----------------------------
     PROFILE
  ----------------------------- */

  const fetchProfile = useCallback(async (sess) => {
    try {
      const res = await apiClient.get("/auth/me", {
        headers: { Authorization: `Bearer ${sess.access_token}` },
      });
      setProfile(res.data);
    } catch {
      try {
        const res = await apiClient.post(
          "/auth/verify",
          {},
          { headers: { Authorization: `Bearer ${sess.access_token}` } }
        );
        setProfile(res.data);
      } catch (err) {
        console.error("❌ Failed to fetch/create profile", err);
      }
    }
  }, []);

  /* -----------------------------
     STARTUPS
  ----------------------------- */

  const fetchStartups = useCallback(async (sess) => {
    try {
      const res = await apiClient.get("/startups", {
        headers: { Authorization: `Bearer ${sess.access_token}` },
      });

      setStartups(res.data || []);

      if (res.data?.length) {
        const savedId = localStorage.getItem("currentStartupId");
        const found = res.data.find((s) => s.id === savedId);
        setCurrentStartup(found || res.data[0]);
      }
    } catch (err) {
      console.error("❌ Failed to fetch startups", err);
    }
    setStartupsLoaded(true);
  }, []);

  /* -----------------------------
     INIT
  ----------------------------- */

  useEffect(() => {
    const init = async () => {
      const { data } = await supabase.auth.getSession();
      const sess = data?.session || null;

      setSession(sess);
      setUser(sess?.user || null);

      if (sess) {
        await Promise.all([fetchProfile(sess), fetchStartups(sess)]);
      } else {
        setStartupsLoaded(true);
      }

      setLoading(false);
    };

    init();

    const { data: listener } = supabase.auth.onAuthStateChange(
      async (_event, sess) => {
        setSession(sess);
        setUser(sess?.user || null);

        if (sess) {
          setStartupsLoaded(false);
          await fetchProfile(sess);
          await fetchStartups(sess);
        } else {
          setProfile(null);
          setStartups([]);
          setCurrentStartup(null);
          setStartupsLoaded(true);
        }
      }
    );

    return () => listener.subscription.unsubscribe();
  }, [fetchProfile, fetchStartups]);

  /* -----------------------------
     ACTIONS
  ----------------------------- */

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
    setSession(null);
    setStartups([]);
    setCurrentStartup(null);
    localStorage.removeItem("currentStartupId");
  };

  const selectStartup = (startup) => {
    setCurrentStartup(startup);
    localStorage.setItem("currentStartupId", startup.id);
  };

  const refreshStartups = async () => {
    if (session) await fetchStartups(session);
  };

  /* -----------------------------
     PERMISSIONS
  ----------------------------- */

  const userRole = useMemo(
    () => currentStartup?.user_role || "member",
    [currentStartup]
  );

  const permissions = useMemo(
    () => ({
      canManageContent: PERMISSIONS.canManageContent(userRole),
      canViewAnalytics: PERMISSIONS.canViewAnalytics(userRole),
      canAccessPitch: PERMISSIONS.canAccessPitch(userRole),
      canManageTeam: PERMISSIONS.canManageTeam(userRole),
      canManageStartup: PERMISSIONS.canManageStartup(userRole),
    }),
    [userRole]
  );

  /* -----------------------------
     PROVIDER
  ----------------------------- */

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        session,
        loading,
        startups,
        startupsLoaded,
        currentStartup,
        selectStartup,
        refreshStartups,
        signOut,
        getAuthHeaders,
        userRole,
        permissions,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
