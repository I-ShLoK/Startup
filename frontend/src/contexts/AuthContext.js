import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { supabase } from '@/lib/supabase';
import axios from 'axios';

const AuthContext = createContext({});
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
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
      if (res.data.length > 0 && !currentStartup) {
        const saved = localStorage.getItem('currentStartupId');
        const found = saved ? res.data.find(s => s.id === saved) : null;
        setCurrentStartup(found || res.data[0]);
      }
    } catch (e) {
      console.error('Failed to fetch startups', e);
    }
  }, [currentStartup]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: sess } }) => {
      setSession(sess);
      setUser(sess?.user ?? null);
      if (sess) {
        fetchProfile(sess);
        fetchStartups(sess);
      }
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, sess) => {
      setSession(sess);
      setUser(sess?.user ?? null);
      if (sess) {
        fetchProfile(sess);
        fetchStartups(sess);
      } else {
        setProfile(null);
        setStartups([]);
        setCurrentStartup(null);
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
    localStorage.removeItem('currentStartupId');
  };

  const selectStartup = (startup) => {
    setCurrentStartup(startup);
    localStorage.setItem('currentStartupId', startup.id);
  };

  const refreshStartups = async () => {
    if (session) await fetchStartups(session);
  };

  return (
    <AuthContext.Provider value={{
      user, profile, session, loading, signOut,
      currentStartup, startups, selectStartup, refreshStartups,
      getAuthHeaders,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
