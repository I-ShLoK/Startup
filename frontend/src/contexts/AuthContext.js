import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { supabase } from '@/lib/supabase';
import axios from 'axios';

const AuthContext = createContext({});
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Permission helpers based on user role in current startup
const PERMISSIONS = {
  canManageContent: (role) => ['founder', 'manager'].includes(role),
  canViewAnalytics: (role) => ['founder', 'manager'].includes(role),
  canAccessPitch: (role) => role === 'founder',
  canManageTeam: (role) => role === 'founder',
  canManageStartup: (role) => role === 'founder',
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startupsLoaded, setStartupsLoaded] = useState(false);
  const [currentStartup, setCurrentStartup] = useState(null);
  const [startups, setStartups] = useState([]);

  const getAuthHeaders = useCallback(() => {
    if (!session?.access_token) return {};
    return { Authorization: `Bearer ${session.access_token}` };
  }, [session]);

  const fetchProfile = useCallback(async (sess) => {
    try {
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${sess.access_token}` },
      });
      setProfile(res.data);
    } catch (e) {
      try {
        const res = await axios.post(`${API}/auth/verify`, {}, {
          headers: { Authorization: `Bearer ${sess.access_token}` },
        });
        setProfile(res.data);
      } catch (err) {
        console.error('Failed to fetch/create profile', err);
      }
    }
  }, []);

  const fetchStartups = useCallback(async (sess) => {
    try {
      const res = await axios.get(`${API}/startups`, {
        headers: { Authorization: `Bearer ${sess.access_token}` },
      });
      setStartups(res.data);
      if (res.data.length > 0) {
        const saved = localStorage.getItem('currentStartupId');
        const found = saved ? res.data.find(s => s.id === saved) : null;
        setCurrentStartup(prev => prev || found || res.data[0]);
      }
    } catch (e) {
      console.error('Failed to fetch startups', e);
    }
    setStartupsLoaded(true);
  }, []);

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session: sess } }) => {
      setSession(sess);
      setUser(sess?.user ?? null);
      if (sess) {
        await Promise.all([fetchProfile(sess), fetchStartups(sess)]);
      } else {
        setStartupsLoaded(true);
      }
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, sess) => {
      setSession(sess);
      setUser(sess?.user ?? null);
      if (sess) {
        setStartupsLoaded(false);
        fetchProfile(sess);
        fetchStartups(sess);
      } else {
        setProfile(null);
        setStartups([]);
        setCurrentStartup(null);
        setStartupsLoaded(true);
      }
    });

    return () => subscription.unsubscribe();
  }, [fetchProfile, fetchStartups]);

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
    setSession(null);
    setStartups([]);
    setCurrentStartup(null);
    setStartupsLoaded(false);
    localStorage.removeItem('currentStartupId');
  };

  const selectStartup = (startup) => {
    setCurrentStartup(startup);
    localStorage.setItem('currentStartupId', startup.id);
  };

  const refreshStartups = async () => {
    if (session) await fetchStartups(session);
  };

  // Get current user's role in the selected startup
  const userRole = useMemo(() => {
    return currentStartup?.user_role || 'member';
  }, [currentStartup]);

  // Permission check functions
  const permissions = useMemo(() => ({
    canManageContent: PERMISSIONS.canManageContent(userRole),
    canViewAnalytics: PERMISSIONS.canViewAnalytics(userRole),
    canAccessPitch: PERMISSIONS.canAccessPitch(userRole),
    canManageTeam: PERMISSIONS.canManageTeam(userRole),
    canManageStartup: PERMISSIONS.canManageStartup(userRole),
  }), [userRole]);

  return (
    <AuthContext.Provider value={{
      user, profile, session, loading, startupsLoaded, signOut,
      currentStartup, startups, selectStartup, refreshStartups,
      getAuthHeaders, userRole, permissions,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
