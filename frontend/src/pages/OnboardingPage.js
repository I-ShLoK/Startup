import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Rocket, ArrowRight } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { session, refreshStartups } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', industry: '', stage: 'idea', website: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Startup name is required'); return; }
    setLoading(true);
    try {
      await axios.post(`${API}/startups`, form, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      await refreshStartups();
      toast.success('Startup created! Welcome to your workspace.');
      navigate('/dashboard');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create startup');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background relative" data-testid="onboarding-page">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent" />
      <div className="w-full max-w-lg relative">
        <Card className="glass-card">
          <CardHeader className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Rocket className="h-7 w-7 text-primary" />
            </div>
            <CardTitle className="text-2xl font-['Plus_Jakarta_Sans']">Set up your startup</CardTitle>
            <CardDescription>Create your workspace to start tracking execution</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <Label>Startup Name *</Label>
                <Input className="mt-1.5 h-11 rounded-xl" placeholder="e.g. Acme Inc" value={form.name} onChange={e => setForm({...form, name: e.target.value})} required data-testid="onboarding-name-input" />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea className="mt-1.5 rounded-xl" placeholder="What does your startup do?" rows={3} value={form.description} onChange={e => setForm({...form, description: e.target.value})} data-testid="onboarding-desc-input" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Industry</Label>
                  <Select value={form.industry} onValueChange={v => setForm({...form, industry: v})}>
                    <SelectTrigger className="mt-1.5 h-11 rounded-xl" data-testid="onboarding-industry-select">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="saas">SaaS</SelectItem>
                      <SelectItem value="fintech">FinTech</SelectItem>
                      <SelectItem value="healthtech">HealthTech</SelectItem>
                      <SelectItem value="edtech">EdTech</SelectItem>
                      <SelectItem value="ecommerce">E-commerce</SelectItem>
                      <SelectItem value="ai_ml">AI / ML</SelectItem>
                      <SelectItem value="marketplace">Marketplace</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Stage</Label>
                  <Select value={form.stage} onValueChange={v => setForm({...form, stage: v})}>
                    <SelectTrigger className="mt-1.5 h-11 rounded-xl" data-testid="onboarding-stage-select">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="idea">Idea</SelectItem>
                      <SelectItem value="mvp">MVP</SelectItem>
                      <SelectItem value="growth">Growth</SelectItem>
                      <SelectItem value="scale">Scale</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Website (optional)</Label>
                <Input className="mt-1.5 h-11 rounded-xl" placeholder="https://yoursite.com" value={form.website} onChange={e => setForm({...form, website: e.target.value})} data-testid="onboarding-website-input" />
              </div>
              <Button type="submit" className="w-full h-11 rounded-xl" disabled={loading} data-testid="onboarding-submit-btn">
                {loading ? 'Creating...' : 'Launch Workspace'} <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
