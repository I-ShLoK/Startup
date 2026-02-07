import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';
import { Presentation, Loader2, Download, RefreshCw } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PitchGeneratorPage() {
  const { currentStartup, getAuthHeaders } = useAuth();
  const [pitch, setPitch] = useState(null);
  const [loading, setLoading] = useState(false);

  const generatePitch = async () => {
    if (!currentStartup) return;
    setLoading(true);
    try {
      const res = await axios.post(`${API}/ai/pitch`, { startup_id: currentStartup.id }, { headers: getAuthHeaders() });
      setPitch(res.data.pitch);
      toast.success('Pitch generated!');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to generate pitch');
    }
    setLoading(false);
  };

  const copyToClipboard = () => {
    if (pitch) {
      navigator.clipboard.writeText(pitch);
      toast.success('Pitch copied to clipboard!');
    }
  };

  if (!currentStartup) return <div className="text-center py-20 text-muted-foreground">Select a startup first</div>;

  return (
    <div className="space-y-6 fade-in" data-testid="pitch-generator-page">
      <div>
        <h1 className="text-2xl font-bold font-['Plus_Jakarta_Sans']">Investor Pitch Generator</h1>
        <p className="text-sm text-muted-foreground">Auto-generate a compelling investor pitch for {currentStartup.name}</p>
      </div>

      <Card className="glass-card">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Presentation className="h-5 w-5 text-primary" /> Pitch Outline
              </CardTitle>
              <CardDescription className="mt-1">
                Uses your startup data, tasks, milestones, and feedback to generate a structured pitch
              </CardDescription>
            </div>
            <div className="flex gap-2">
              {pitch && (
                <Button variant="outline" onClick={copyToClipboard} className="rounded-full" data-testid="copy-pitch-btn">
                  <Download className="h-4 w-4 mr-1" /> Copy
                </Button>
              )}
              <Button onClick={generatePitch} disabled={loading} className="rounded-full" data-testid="generate-pitch-btn">
                {loading ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Generating...</> :
                 pitch ? <><RefreshCw className="h-4 w-4 mr-1" /> Regenerate</> : <><Presentation className="h-4 w-4 mr-1" /> Generate Pitch</>}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {pitch ? (
            <div className="markdown-content prose prose-sm max-w-none bg-muted/30 p-6 rounded-xl border border-border/30" data-testid="pitch-content">
              {pitch.split('\n').map((line, i) => {
                if (line.startsWith('### ')) return <h3 key={i}>{line.replace('### ', '')}</h3>;
                if (line.startsWith('## ')) return <h2 key={i}>{line.replace('## ', '')}</h2>;
                if (line.startsWith('# ')) return <h1 key={i}>{line.replace('# ', '')}</h1>;
                if (line.startsWith('**') && line.endsWith('**')) return <p key={i}><strong>{line.replace(/\*\*/g, '')}</strong></p>;
                if (line.startsWith('- ') || line.startsWith('* ')) return <li key={i} className="ml-4">{line.replace(/^[-*]\s/, '').replace(/\*\*(.*?)\*\*/g, '$1')}</li>;
                if (line.match(/^\d+\./)) return <li key={i} className="ml-4 list-decimal">{line.replace(/^\d+\.\s*/, '').replace(/\*\*(.*?)\*\*/g, '$1')}</li>;
                if (line.trim() === '') return <br key={i} />;
                return <p key={i}>{line.replace(/\*\*(.*?)\*\*/g, '$1')}</p>;
              })}
            </div>
          ) : (
            <div className="text-center py-16 text-muted-foreground">
              <Presentation className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
              <p className="text-lg font-medium mb-1">Generate Your Investor Pitch</p>
              <p className="text-sm">The AI will analyze your startup data and create a structured pitch outline with:</p>
              <ul className="text-sm mt-3 space-y-1">
                <li>Problem Statement & Solution</li>
                <li>Market Opportunity (TAM/SAM/SOM)</li>
                <li>Traction & Key Metrics</li>
                <li>Business Model & Roadmap</li>
              </ul>
              <p className="text-xs mt-4 text-muted-foreground/70">Powered by Google Gemini AI</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
