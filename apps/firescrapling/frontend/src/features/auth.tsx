import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Flame, LogIn, UserPlus, Mail, Lock, User, AlertCircle, Loader2 } from 'lucide-react';
import { rpcCall } from '../api';

export interface UserData {
  id: string;
  email: string;
  full_name: string | null;
}

interface AuthProps {
  onLogin: (user: UserData) => void;
}

export function AuthView({ onLogin }: AuthProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'login' | 'register'>('login');

  // Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await rpcCall({ func: 'login_user', args: { email, password } });
      if (res.success) {
        onLogin(res.user);
      } else {
        setError(res.error || 'Login failed');
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await rpcCall({ func: 'register_user', args: { email, password, full_name: fullName } });
      if (res.success) {
        // Auto-login after registration
        onLogin(res.user);
      } else {
        setError(res.error || 'Registration failed');
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 overflow-hidden relative">
      <div className="absolute inset-0 bg-dot-grid opacity-[0.1] pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent pointer-events-none" />
      
      <div className="w-full max-w-[400px] z-10 animate-in fade-in zoom-in duration-500">
        <div className="flex flex-col items-center mb-8 space-y-4">
          <div className="bg-gradient-to-br from-orange-500 to-red-600 p-4 rounded-2xl shadow-2xl shadow-orange-500/20">
            <Flame className="h-8 w-8 text-white animate-pulse" />
          </div>
          <div className="text-center">
            <h1 className="text-3xl font-heading font-black tracking-tighter text-white">FIRESCRAPLING</h1>
            <p className="text-muted-foreground text-xs uppercase tracking-widest font-bold mt-1">Extraction Platform</p>
          </div>
        </div>

        <Tabs value={tab} onValueChange={(v: any) => setTab(v)} className="w-full">
          <TabsList className="grid w-full grid-cols-2 bg-zinc-900/50 border border-white/5 h-12">
            <TabsTrigger value="login" className="data-[state=active]:bg-orange-600 data-[state=active]:text-white font-bold text-xs">
              <LogIn className="h-3 w-3 mr-2" /> LOGIN
            </TabsTrigger>
            <TabsTrigger value="register" className="data-[state=active]:bg-orange-600 data-[state=active]:text-white font-bold text-xs">
              <UserPlus className="h-3 w-3 mr-2" /> REGISTER
            </TabsTrigger>
          </TabsList>

          <TabsContent value="login" className="mt-4">
            <Card className="bg-zinc-900/40 border-white/5 backdrop-blur-xl">
              <form onSubmit={handleLogin}>
                <CardHeader>
                  <CardTitle className="text-lg font-heading">Welcome Back</CardTitle>
                  <CardDescription>Enter your credentials to access your scrapes.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {error && (
                    <div className="bg-red-500/10 border border-red-500/20 p-3 rounded-lg flex items-center gap-2 text-xs text-red-400">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {error}
                    </div>
                  )}
                  <div className="space-y-2">
                    <Label className="text-[10px] uppercase font-bold text-muted-foreground">Email</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input 
                        type="email" 
                        placeholder="name@example.com" 
                        className="pl-10 bg-black/20 border-white/10"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[10px] uppercase font-bold text-muted-foreground">Password</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input 
                        type="password" 
                        placeholder="••••••••" 
                        className="pl-10 bg-black/20 border-white/10"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button type="submit" className="w-full bg-orange-600 hover:bg-orange-700 font-bold" disabled={loading}>
                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <LogIn className="h-4 w-4 mr-2" />}
                    SIGN IN
                  </Button>
                </CardFooter>
              </form>
            </Card>
          </TabsContent>

          <TabsContent value="register" className="mt-4">
            <Card className="bg-zinc-900/40 border-white/5 backdrop-blur-xl">
              <form onSubmit={handleRegister}>
                <CardHeader>
                  <CardTitle className="text-lg font-heading">Create Account</CardTitle>
                  <CardDescription>Start extracting LLM-ready data today.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {error && (
                    <div className="bg-red-500/10 border border-red-500/20 p-3 rounded-lg flex items-center gap-2 text-xs text-red-400">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {error}
                    </div>
                  )}
                  <div className="space-y-2">
                    <Label className="text-[10px] uppercase font-bold text-muted-foreground">Full Name</Label>
                    <div className="relative">
                      <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input 
                        placeholder="John Doe" 
                        className="pl-10 bg-black/20 border-white/10"
                        value={fullName}
                        onChange={e => setFullName(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[10px] uppercase font-bold text-muted-foreground">Email</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input 
                        type="email" 
                        placeholder="name@example.com" 
                        className="pl-10 bg-black/20 border-white/10"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[10px] uppercase font-bold text-muted-foreground">Password</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input 
                        type="password" 
                        placeholder="••••••••" 
                        className="pl-10 bg-black/20 border-white/10"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button type="submit" className="w-full bg-orange-600 hover:bg-orange-700 font-bold" disabled={loading}>
                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <UserPlus className="h-4 w-4 mr-2" />}
                    CREATE ACCOUNT
                  </Button>
                </CardFooter>
              </form>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="mt-8 text-center">
           <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-[0.2em]">
             Secured by FireScrapling Stealth Engine
           </p>
        </div>
      </div>
    </div>
  );
}
