import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Lightbulb, Sparkles, Target, TrendingUp, Loader2 } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const insightTypes = [
  { key: 'general', label: 'General Insights', icon: Lightbulb, desc: 'Get overall analysis and actionable recommendations' },
  { key: 'tasks', label: 'Task Suggestions', icon: Rocket, desc: 'Get AI-suggested tasks based on your startup stage' },
  { key: 'milestones', label: 'Milestone Ideas', icon: Target, desc: 'Discover key milestones you should be tracking' },
  { key: 'growth', label: 'Growth Strategy', icon: TrendingUp, desc: 'Get growth strategies tailored to your startup' },
];

export default function AIInsightsPage() {
  const { currentStartup, getAuthHeaders } = useAuth();
  const [insights, setInsights] = useState({});
  const [loading, setLoading] = useState({});
  const [activeTab, setActiveTab] = useState('general');

  const generateInsight = async (type) => {
    if (!currentStartup) return;
    setLoading(prev => ({ ...prev, [type]: true }));
    try {
      const res = await axios.post(`${API}/ai/insights`, {
        startup_id: currentStartup.id,
        prompt_type: type,
      }, { headers: getAuthHeaders() });
      setInsights(prev => ({ ...prev, [type]: res.data.insights }));
      toast.success('Insights generated!');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to generate insights');
    }
    setLoading(prev => ({ ...prev, [type]: false }));
  };

  if (!currentStartup) return <div className="text-center py-20 text-muted-foreground">Select a startup first</div>;

  return (
    <div className="space-y-6 fade-in" data-testid="ai-insights-page">
      <div>
        <h1 className="text-2xl font-bold font-['Plus_Jakarta_Sans']">AI Insights</h1>
        <p className="text-sm text-muted-foreground">Get AI-powered suggestions and analysis for {currentStartup.name}</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-4 w-full max-w-2xl">
          {insightTypes.map(t => (
            <TabsTrigger key={t.key} value={t.key} data-testid={`insight-tab-${t.key}`}>
              <t.icon className="h-4 w-4 mr-1.5" /><span className="hidden sm:inline">{t.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        {insightTypes.map(t => (
          <TabsContent key={t.key} value={t.key}>
            <Card className="glass-card">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2"><t.icon className="h-5 w-5 text-primary" />{t.label}</CardTitle>
                    <CardDescription className="mt-1">{t.desc}</CardDescription>
                  </div>
                  <Button onClick={() => generateInsight(t.key)} disabled={loading[t.key]} className="rounded-full" data-testid={`generate-${t.key}-btn`}>
                    {loading[t.key] ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Generating...</> : <><Lightbulb className="h-4 w-4 mr-1" /> Generate</>}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {insights[t.key] ? (
                  <div className="markdown-content prose prose-sm max-w-none" data-testid={`insight-content-${t.key}`}>
                    {insights[t.key].split('\n').map((line, i) => {
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
                  <div className="text-center py-12 text-muted-foreground">
                    <t.icon className="h-12 w-12 mx-auto mb-4 text-muted-foreground/30" />
                    <p>Click "Generate" to get AI-powered {t.label.toLowerCase()}</p>
                    <p className="text-xs mt-1">Powered by Google Gemini</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
