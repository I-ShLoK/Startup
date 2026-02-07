import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Loader2 } from 'lucide-react';

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const url = new URL(window.location.href);
        const code = url.searchParams.get('code');
        const errorParam = url.searchParams.get('error');
        const errorDescription = url.searchParams.get('error_description');

        if (errorParam) {
          setError(errorDescription || errorParam);
          setTimeout(() => navigate('/auth'), 3000);
          return;
        }

        if (code) {
          const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) {
            setError(exchangeError.message);
            setTimeout(() => navigate('/auth'), 3000);
            return;
          }
        }

        // Session should now be established via onAuthStateChange in AuthContext
        // Small delay to let AuthContext pick up the session
        setTimeout(() => navigate('/dashboard'), 500);
      } catch (err) {
        console.error('Auth callback error:', err);
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
