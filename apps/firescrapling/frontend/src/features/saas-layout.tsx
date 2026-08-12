import React from 'react';
import { 
  LayoutDashboard, 
  Key, 
  Terminal, 
  Webhook, 
  BarChart3, 
  Settings, 
  ChevronLeft, 
  ChevronRight, 
  Menu, 
  Moon, 
  Sun, 
  Bell, 
  User, 
  CreditCard,
  LogOut,
  Search,
  Zap,
  Flame
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuLabel, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '../components/ui/dropdown-menu';
import { ScrollArea } from '../components/ui/scroll-area';

export interface NavItem {
  id: string;
  label: string;
  icon: any;
}

const navItems: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'api-keys', label: 'API Keys', icon: Key },
  { id: 'playground', label: 'Playground', icon: Terminal },
  { id: 'webhooks', label: 'Webhooks', icon: Webhook },
  { id: 'usage', label: 'Usage & Billing', icon: BarChart3 },
  { id: 'settings', label: 'Settings', icon: Settings },
];

interface LayoutProps {
  activeView: string;
  onViewChange: (id: string) => void;
  onLogout?: () => void;
  userEmail?: string;
  children: React.ReactNode;
}

export function DashboardLayout({ activeView, onViewChange, onLogout, userEmail, children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = React.useState(true);
  const [isDark, setIsDark] = React.useState(true);

  return (
    <div className={cn("min-h-screen flex bg-background text-foreground transition-colors duration-300", isDark ? "dark" : "")}>
      {/* Sidebar */}
      <aside className={cn(
        "hidden md:flex flex-col border-r bg-card/40 backdrop-blur-xl transition-all duration-300 ease-in-out fixed inset-y-0 z-50",
        sidebarOpen ? "w-64" : "w-20"
      )}>
        <div className="h-16 flex items-center px-6 border-b">
          <div className="flex items-center gap-3">
            <div className="bg-primary p-2 rounded-lg shadow-lg shadow-primary/20">
              <Flame className="h-5 w-5 text-white" />
            </div>
            {sidebarOpen && (
              <span className="font-heading font-black tracking-tighter text-xl text-white">
                FIRESCRAILING
              </span>
            )}
          </div>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onViewChange(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group",
                  activeView === item.id 
                    ? "bg-primary text-primary-foreground shadow-md shadow-primary/10" 
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
              >
                <item.icon className={cn("h-4 w-4 shrink-0", activeView === item.id ? "text-white" : "text-primary")} />
                {sidebarOpen && <span>{item.label}</span>}
              </button>
            ))}
          </nav>
        </ScrollArea>

        <div className="p-4 border-t bg-muted/5">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-full justify-center text-muted-foreground hover:text-foreground"
          >
            {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className={cn(
        "flex-1 flex flex-col transition-all duration-300",
        sidebarOpen ? "md:pl-64" : "md:pl-20"
      )}>
        {/* Header */}
        <header className="h-16 border-b bg-background/60 backdrop-blur-lg flex items-center justify-between px-6 sticky top-0 z-40">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" />
            </Button>
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input 
                placeholder="Search documentation..." 
                className="bg-muted/50 border border-border/50 rounded-full py-2 pl-10 pr-4 text-xs w-64 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Badge variant="outline" className="hidden lg:flex items-center gap-2 bg-emerald-500/5 text-emerald-500 border-emerald-500/20 py-1 px-3">
              <Zap className="h-3 w-3 fill-current" />
              <span className="text-[10px] font-bold uppercase tracking-widest">4,820 Credits Left</span>
            </Badge>

            <div className="flex items-center gap-1 border-r pr-4 mr-2 border-border/50">
              <Button variant="ghost" size="icon" onClick={() => setIsDark(!isDark)} className="text-muted-foreground">
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <Button variant="ghost" size="icon" className="text-muted-foreground">
                <Bell className="h-4 w-4" />
              </Button>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-3 hover:opacity-80 transition-opacity outline-none">
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white shadow-lg">
                    {(userEmail || '?').slice(0, 2).toUpperCase()}
                  </div>
                  <div className="hidden sm:block text-left">
                    <p className="text-xs font-bold leading-none">{userEmail || 'Signed in'}</p>
                    <p className="text-[10px] text-muted-foreground">Free Plan</p>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem><User className="mr-2 h-4 w-4" /> Profile</DropdownMenuItem>
                <DropdownMenuItem><CreditCard className="mr-2 h-4 w-4" /> Billing</DropdownMenuItem>
                <DropdownMenuItem><Settings className="mr-2 h-4 w-4" /> Settings</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-red-500" onClick={onLogout}><LogOut className="mr-2 h-4 w-4" /> Logout</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
