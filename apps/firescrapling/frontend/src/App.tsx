import React, { useState, useEffect, useCallback } from 'react';
import { Button } from './components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from './components/ui/card';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Switch } from './components/ui/switch';
import { Progress } from './components/ui/progress';
import { Separator } from './components/ui/separator';
import { Badge } from './components/ui/badge';
import { ScrollArea } from './components/ui/scroll-area';
import { Textarea } from './components/ui/textarea';
import { 
  Flame, 
  Globe, 
  Zap, 
  Shield, 
  Layers, 
  Play, 
  History, 
  Search, 
  Plus,
  LayoutDashboard,
  Database,
  Terminal,
  Settings,
  Menu,
  X,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Code2,
  Cpu,
  Sparkles,
  Braces,
  BrainCircuit,
  FileJson,
  BookOpen,
  LogOut,
  User as UserIcon,
  BarChart4,
  Webhook,
  ShieldCheck,
  Activity
} from 'lucide-react';
import { cn } from './lib/utils';
import { getSessionToken, logoutUser } from './restClient';
import { ApiDocsView } from './features/docs';
import { AuthView, UserData } from './features/auth';
import { DashboardLayout } from './features/saas-layout';
import { SaaSOverview } from './features/saas-overview';
import { SaaSPlayground } from './features/saas-playground';
import { SaaSApiKeys } from './features/saas-api-keys';
import { LandingHero, FeaturesGrid } from './features/landing';
import { SaaSInternalPricing } from './features/pricing';
import { AdminDashboard } from './features/admin-dashboard';

export default function App() {
  const [user, setUser] = useState<UserData | null>(() => {
    // A cached user without a session token is stale — the token is what the API trusts.
    if (!getSessionToken()) {
      localStorage.removeItem('firescrapling_user');
      return null;
    }
    const saved = localStorage.getItem('firescrapling_user');
    try {
      return saved ? (JSON.parse(saved) as UserData) : null;
    } catch {
      return null;
    }
  });

  const [activeView, setActiveView] = useState<string>('landing');
  // Admin console is still backed by placeholder data; opt in explicitly.
  const adminDemoEnabled = import.meta.env.VITE_ADMIN_DEMO === 'true';

  const handleLogin = (userData: UserData) => {
    localStorage.setItem('firescrapling_user', JSON.stringify(userData));
    setUser(userData);
    setActiveView('overview');
  };

  const handleLogout = () => {
    void logoutUser();
    localStorage.removeItem('firescrapling_user');
    setUser(null);
    setActiveView('landing');
  };

  if (!user && activeView !== 'landing' && activeView !== 'pricing' && activeView !== 'docs') {
    return <AuthView onLogin={handleLogin} />;
  }

  const renderContent = () => {
    switch (activeView) {
      case 'landing':
        return (
          <div className="bg-background min-h-screen">
             <LandingHero 
               onGetStarted={() => setActiveView('overview')} 
               onViewDocs={() => setActiveView('docs')} 
             />
             <FeaturesGrid />
          </div>
        );
      case 'pricing':
        return <SaaSInternalPricing />;
      case 'overview':
        return <SaaSOverview />;
      case 'playground':
        return <SaaSPlayground />;
      case 'api-keys':
        return <SaaSApiKeys />;
      case 'docs':
        return <ApiDocsView />;
      case 'admin':
        return <AdminDashboard />;
      case 'webhooks':
        return (
          <div className="p-12 text-center space-y-4 opacity-50 grayscale transition-all hover:grayscale-0 hover:opacity-100">
             <div className="p-6 rounded-full bg-primary/5 border border-primary/10 inline-block">
                <Webhook className="h-12 w-12 text-primary animate-pulse" />
             </div>
             <div className="space-y-1">
               <h3 className="text-lg font-heading font-black text-white">WEBHOOKS ENGINE</h3>
               <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Connect your production endpoints for real-time extraction events.</p>
               <Badge className="mt-4 bg-primary text-primary-foreground font-black uppercase tracking-widest">Enterprise Feature</Badge>
             </div>
          </div>
        );
      case 'usage':
        return (
          <div className="p-12 text-center space-y-4 opacity-50 grayscale transition-all hover:grayscale-0 hover:opacity-100">
             <div className="p-6 rounded-full bg-amber-500/5 border border-amber-500/10 inline-block">
                <BarChart4 className="h-12 w-12 text-amber-500 animate-pulse" />
             </div>
             <div className="space-y-1">
               <h3 className="text-lg font-heading font-black text-white">USAGE & BILLING</h3>
               <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Detailed breakdown of credits consumed per extraction engine.</p>
               <Badge className="mt-4 bg-amber-500 text-black font-black uppercase tracking-widest">Pro Plan Active</Badge>
             </div>
          </div>
        );
      default:
        return <SaaSOverview />;
    }
  };

  // Standalone Landing/Pricing/Docs Shell (Public)
  if (activeView === 'landing' || activeView === 'pricing' || activeView === 'docs') {
    return (
      <div className="min-h-screen bg-background text-foreground dark selection:bg-orange-500/30 selection:text-orange-100">
        <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-background/60 backdrop-blur-xl h-16 flex items-center justify-between px-6 md:px-12">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setActiveView('landing')}>
             <div className="bg-orange-600 p-1.5 rounded-lg shadow-xl shadow-orange-600/20">
                <Flame className="h-4 w-4 text-white" />
             </div>
             <span className="font-heading font-black tracking-tighter text-xl text-white">FIRESCRAPLING</span>
          </div>
          <div className="flex items-center gap-6">
             <nav className="hidden md:flex items-center gap-8 text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                <button onClick={() => setActiveView('landing')} className={cn("hover:text-white transition-colors", activeView === 'landing' && "text-white")}>Features</button>
                <button onClick={() => setActiveView('pricing')} className={cn("hover:text-white transition-colors", activeView === 'pricing' && "text-white")}>Pricing</button>
                <button onClick={() => setActiveView('docs')} className={cn("hover:text-white transition-colors", activeView === 'docs' && "text-white")}>API Docs</button>
             </nav>
             <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={() => setActiveView('overview')} className="text-[10px] font-black uppercase tracking-widest">Log In</Button>
                <Button size="sm" onClick={() => setActiveView('overview')} className="bg-orange-600 text-white font-black uppercase tracking-widest shadow-xl shadow-orange-600/20 px-6">Sign Up</Button>
             </div>
          </div>
        </header>
        <div className="pt-16">
          {renderContent()}
        </div>
      </div>
    );
  }

  // Admin Shell (Full Screen)
  if (activeView === 'admin') {
    return (
      <div className="min-h-screen bg-[#F9FAFB] text-[#111827]">
        <AdminDashboard />
        <Button 
          onClick={() => setActiveView('overview')}
          className="fixed bottom-6 right-6 bg-black text-white font-bold text-xs uppercase tracking-widest shadow-2xl z-[100]"
        >
          Exit Admin Mode
        </Button>
      </div>
    );
  }

  // Standard User Dashboard Shell
  return (
    <DashboardLayout
      activeView={activeView}
      onViewChange={setActiveView}
      onLogout={handleLogout}
      userEmail={user?.email}
    >
      <div className="dark relative">
        {adminDemoEnabled && (
          <div className="absolute top-4 right-4 z-50">
            <Button 
              size="sm" 
              onClick={() => setActiveView('admin')}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-black text-[10px] uppercase tracking-widest shadow-lg shadow-emerald-600/20"
            >
              <ShieldCheck className="h-3 w-3 mr-2" /> Admin Panel (Demo)
            </Button>
          </div>
        )}
        {renderContent()}
      </div>
    </DashboardLayout>
  );
}
