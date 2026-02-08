import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { BarChart3, CheckCircle2, ClipboardList, Home, IndianRupee, Lightbulb, LogOut, Menu, MessageSquare, Moon, Presentation, Rocket, Settings, Sun, Target, Users, X, Briefcase } from 'lucide-react';
import { useState, useMemo } from 'react';

// Base nav items with permission requirements
const allNavItems = [
  { to: '/dashboard', icon: Home, label: 'Overview', end: true, requiresPermission: null },
  { to: '/dashboard/tasks', icon: ClipboardList, label: 'Tasks', requiresPermission: null },
  { to: '/dashboard/milestones', icon: Target, label: 'Milestones', requiresPermission: null },
  { to: '/dashboard/feedback', icon: MessageSquare, label: 'Feedback', requiresPermission: null },
  { to: '/dashboard/finance', icon: IndianRupee, label: 'Finance', requiresPermission: null },
  { to: '/dashboard/analytics', icon: BarChart3, label: 'Analytics', requiresPermission: 'canViewAnalytics' },
  { to: '/dashboard/ai-insights', icon: Lightbulb, label: 'AI Insights', requiresPermission: 'canViewAnalytics' },
  { to: '/dashboard/pitch', icon: Presentation, label: 'Pitch Generator', requiresPermission: 'canAccessPitch' },
  { to: '/dashboard/investors', icon: Briefcase, label: 'Investors', requiresPermission: null },
  { to: '/dashboard/team', icon: Users, label: 'Team', requiresPermission: null },
  { to: '/dashboard/settings', icon: Settings, label: 'Settings', requiresPermission: null },
];

// Role badge colors
const roleBadgeColors = {
  founder: 'bg-primary/20 text-primary border-primary/30',
  manager: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  member: 'bg-muted text-muted-foreground border-border',
};

export default function DashboardLayout() {
  const { profile, signOut, currentStartup, startups, selectStartup, userRole, permissions } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const initials = (profile?.full_name || profile?.email || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  // Filter nav items based on user permissions
  const navItems = useMemo(() => {
    return allNavItems.filter(item => {
      if (!item.requiresPermission) return true;
      return permissions[item.requiresPermission];
    });
  }, [permissions]);

  const SidebarContent = () => (
    <>
      <div className="p-4 border-b border-border/40">
        <div className="flex items-center gap-2 mb-4">
          <Rocket className="h-6 w-6 text-primary" />
          <span className="text-lg font-bold font-['Plus_Jakarta_Sans']">StartupOps</span>
        </div>
        {startups.length > 0 && (
          <Select value={currentStartup?.id || ''} onValueChange={(v) => { const s = startups.find(st => st.id === v); if (s) selectStartup(s); }}>
            <SelectTrigger className="h-9 rounded-lg text-sm" data-testid="startup-selector">
              <SelectValue placeholder="Select startup" />
            </SelectTrigger>
            <SelectContent>
              {startups.map(s => (
                <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {/* Role Badge */}
        {userRole && (
          <div className="mt-3 flex items-center justify-center">
            <Badge variant="outline" className={`text-xs capitalize ${roleBadgeColors[userRole] || roleBadgeColors.member}`}>
              {userRole}
            </Badge>
          </div>
        )}
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-accent hover:text-foreground'}`}
            data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-border/40 space-y-3">
        <Button variant="ghost" size="sm" className="w-full justify-start gap-2" onClick={toggleTheme} data-testid="theme-toggle-sidebar">
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="w-full justify-start gap-3 h-auto py-2" data-testid="user-menu-trigger">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-primary/10 text-primary text-xs">{initials}</AvatarFallback>
              </Avatar>
              <div className="text-left truncate">
                <p className="text-sm font-medium truncate">{profile?.full_name || 'User'}</p>
                <p className="text-xs text-muted-foreground truncate">{profile?.email}</p>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => navigate('/dashboard/settings')} data-testid="menu-settings">
              <Settings className="mr-2 h-4 w-4" /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={signOut} className="text-destructive" data-testid="menu-logout">
              <LogOut className="mr-2 h-4 w-4" /> Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-background" data-testid="dashboard-layout">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-64 glass-sidebar" data-testid="sidebar-desktop">
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-64 h-full flex flex-col glass-sidebar z-10">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile Header */}
        <header className="lg:hidden flex items-center justify-between p-4 border-b border-border/40">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)} data-testid="mobile-menu-btn">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-2">
            <Rocket className="h-5 w-5 text-primary" />
            <span className="font-bold">StartupOps</span>
          </div>
          <Button variant="ghost" size="icon" onClick={toggleTheme}>
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
