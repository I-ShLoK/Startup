import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Loader2 } from 'lucide-react';

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('Processing...');

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const url = new URL(window.location.href);
        const code = url.searchParams.get('code');
        const errorParam = url.searchParams.get('error');
        const errorDescription = url.searchParams.get('error_description');

        console.log('[AuthCallback] Processing callback, code present:', !!code);

        if (errorParam) {
          setError(errorDescription || errorParam);
          setTimeout(() => navigate('/auth'), 3000);
          return;
        }

        if (code) {
          setStatus('Exchanging code for session...');
          const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) {
            console.error('[AuthCallback] Exchange error:', exchangeError);
            setError(exchangeError.message);
            setTimeout(() => navigate('/auth'), 3000);
            return;
          }
          console.log('[AuthCallback] Session established:', !!data?.session);
        }

        // Wait for session to be fully established and verify it
        setStatus('Verifying session...');
        let attempts = 0;
        const maxAttempts = 10;
        
        const checkSession = async () => {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            console.log('[AuthCallback] Session verified, redirecting...');
            navigate('/dashboard');
          } else if (attempts < maxAttempts) {
            attempts++;
            setTimeout(checkSession, 300);
          } else {
            console.error('[AuthCallback] Session verification timeout');
            setError('Session verification failed. Please try again.');
            setTimeout(() => navigate('/auth'), 3000);
          }
        };
        
        // Start checking session after a brief delay
        setTimeout(checkSession, 500);
        
      } catch (err) {
        console.error('[AuthCallback] Error:', err);
        setError('Authentication failed. Redirecting...');
        setTimeout(() => navigate('/auth'), 3000);
      }
    };

    handleCallback();
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background" data-testid="auth-callback-page">
      <div className="text-center space-y-4">
        {error ? (
          <>
            <p className="text-destructive text-lg">{error}</p>
            <p className="text-muted-foreground text-sm">Redirecting to login...</p>
          </>
        ) : (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
            <p className="text-muted-foreground">Completing sign in...</p>
          </>
        )}
      </div>
    </div>
  );
}
