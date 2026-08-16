import React, { useState, useEffect } from 'react';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';
import { BarChart4, Flame } from 'lucide-react';
import { cn } from './lib/utils';
import { getSessionToken, logoutUser, getCapabilities, PlatformCapabilities } from './api';
import { ApiDocsView } from './docs/api-docs';
import { AuthView, UserData } from './features/auth';
import { DashboardLayout } from './app/saas-layout';
import { SaaSOverview } from './app/saas-overview';
import { SaaSPlayground } from './app/saas-playground';
import { SaaSApiKeys } from './app/saas-api-keys';
import { LandingHero, FeaturesGrid } from './marketing/landing';
import { SaaSInternalPricing } from './marketing/pricing';
import { AdminDashboard } from './admin/dashboard';
import { SaaSWebhooks } from './app/saas-webhooks';
import { SaaSProviders } from './app/saas-providers';
import { SaaSSavings } from './app/saas-savings';
import { SaaSSettings } from './app/saas-settings';

const GITHUB_URL = 'https://github.com/firescrapling/firescrapling';

export default function App() {
  const [user, setUser] = useState<UserData | null>(() => {
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
  const [caps, setCaps] = useState<PlatformCapabilities | null>(null);

  useEffect(() => {
    void getCapabilities()
      .then(setCaps)
      .catch(() => setCaps(null));
  }, []);

  const hosted = caps?.hosted === true;

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

  const publicViews = new Set(['landing', 'docs', ...(hosted ? (['pricing'] as const) : [])]);

  if (!user && !publicViews.has(activeView)) {
    return <AuthView onLogin={handleLogin} />;
  }

  const renderContent = () => {
    switch (activeView) {
      case 'landing':
        return (
          <div className="bg-background min-h-screen">
            <LandingHero onViewDocs={() => setActiveView('docs')} />
            <FeaturesGrid />
          </div>
        );
      case 'pricing':
        return hosted ? <SaaSInternalPricing /> : <LandingHero onViewDocs={() => setActiveView('docs')} />;
      case 'overview':
        return <SaaSOverview onNavigate={setActiveView} />;
      case 'playground':
        return <SaaSPlayground />;
      case 'api-keys':
        return <SaaSApiKeys />;
      case 'providers':
        return <SaaSProviders />;
      case 'savings':
        return <SaaSSavings />;
      case 'settings':
        return <SaaSSettings />;
      case 'docs':
        return <ApiDocsView />;
      case 'admin':
        return <AdminDashboard />;
      case 'webhooks':
        return <SaaSWebhooks />;
      case 'usage':
        return (
          <div className="p-12 text-center space-y-4">
            <div className="p-6 rounded-full bg-orange-500/5 border border-orange-500/10 inline-block">
              <BarChart4 className="h-12 w-12 text-orange-500" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-heading font-black text-white">USAGE</h3>
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
                Request counts and latency live under Overview. Estimated fetch savings are on Savings.
              </p>
              {hosted && (
                <Badge className="mt-4 bg-amber-500 text-black font-black uppercase tracking-widest">
                  Hosted billing available
                </Badge>
              )}
            </div>
          </div>
        );
      default:
        return <SaaSOverview />;
    }
  };

  if (activeView === 'landing' || activeView === 'docs' || (hosted && activeView === 'pricing')) {
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
              <button
                onClick={() => setActiveView('landing')}
                className={cn('hover:text-white transition-colors', activeView === 'landing' && 'text-white')}
              >
                Features
              </button>
              <button
                onClick={() => setActiveView('docs')}
                className={cn('hover:text-white transition-colors', activeView === 'docs' && 'text-white')}
              >
                Docs
              </button>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
                className="hover:text-white transition-colors"
              >
                GitHub
              </a>
              {hosted && (
                <button
                  onClick={() => setActiveView('pricing')}
                  className={cn('hover:text-white transition-colors', activeView === 'pricing' && 'text-white')}
                >
                  Pricing
                </button>
              )}
            </nav>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActiveView('overview')}
                className="text-[10px] font-black uppercase tracking-widest"
              >
                Log In
              </Button>
              <Button
                size="sm"
                onClick={() => setActiveView('overview')}
                className="bg-orange-600 text-white font-black uppercase tracking-widest shadow-xl shadow-orange-600/20 px-6"
              >
                Open dashboard
              </Button>
            </div>
          </div>
        </header>
        <div className="pt-16">{renderContent()}</div>
      </div>
    );
  }

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

  return (
    <DashboardLayout
      activeView={activeView}
      onViewChange={setActiveView}
      onLogout={handleLogout}
      userEmail={user?.email}
    >
      <div className="dark relative">{renderContent()}</div>
    </DashboardLayout>
  );
}
