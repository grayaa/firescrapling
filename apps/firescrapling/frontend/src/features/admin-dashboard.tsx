import React, { useCallback, useEffect, useState } from 'react';
import {
  Shield,
  Users,
  Activity,
  Server,
  AlertTriangle,
  Search,
  MoreHorizontal,
  CreditCard,
  Settings,
  CheckCircle2,
  Zap,
  RefreshCcw,
  Trash2,
  Loader2,
  Lock,
  Briefcase,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  AdminHealth,
  AdminJob,
  AdminStats,
  AdminUser,
  RestApiError,
  deleteAdminJob,
  deleteAdminUser,
  getAdminHealth,
  getAdminStats,
  getAdminToken,
  getCapabilities,
  listAdminJobs,
  listAdminUsers,
  setAdminToken,
} from '../restClient';

type TabId = 'overview' | 'users' | 'jobs' | 'billing' | 'settings';

const PAGE_SIZE = 20;

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    return new Date(value.includes('T') ? value : value.replace(' ', 'T') + 'Z').toLocaleDateString();
  } catch {
    return value;
  }
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '…' : s;
}

function errMessage(e: unknown): string {
  if (e instanceof RestApiError) return e.message;
  if (e instanceof Error) return e.message;
  return 'Request failed';
}

// --- Login gate ---

function AdminLoginGate({ onAuthed }: { onAuthed: () => void }) {
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setAdminToken(token.trim());
    try {
      await getAdminHealth();
      onAuthed();
    } catch (err) {
      setAdminToken('');
      setError(errMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6 font-sans antialiased">
      <Card className="w-full max-w-md shadow-none border-gray-200 rounded-lg bg-white">
        <CardHeader className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="bg-black p-1.5 rounded-md">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <CardTitle className="text-sm font-bold uppercase tracking-tight">FireScrapling Admin</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Enter the <code className="text-[10px] bg-gray-100 px-1 rounded">ADMIN_SECRET</code> configured on
            the API server.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-3.5 w-3.5 text-gray-400" />
              <Input
                type="password"
                value={token}
                onChange={(ev) => setToken(ev.target.value)}
                placeholder="Admin secret"
                className="h-9 pl-9 bg-gray-50 border-gray-200 text-xs"
                autoFocus
                disabled={busy}
              />
            </div>
            {error && (
              <p className="text-xs font-semibold text-red-600">{error}</p>
            )}
            <Button
              type="submit"
              disabled={busy || !token.trim()}
              className="w-full h-9 text-[10px] font-bold uppercase bg-black text-white hover:bg-gray-800"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> : null}
              Unlock Admin
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

// --- Main dashboard ---

export function AdminDashboard() {
  const [authed, setAuthed] = useState(() => Boolean(getAdminToken()));
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [hosted, setHosted] = useState(false);

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersOffset, setUsersOffset] = useState(0);
  const [userSearch, setUserSearch] = useState('');
  const [userSearchInput, setUserSearchInput] = useState('');
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);

  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsOffset, setJobsOffset] = useState(0);
  const [jobStatus, setJobStatus] = useState('');
  const [jobType, setJobType] = useState('');
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState<string | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);

  const handleUnauthorized = useCallback((err: unknown) => {
    if (err instanceof RestApiError && (err.status === 401 || err.status === 503)) {
      setAdminToken('');
      setAuthed(false);
      return true;
    }
    return false;
  }, []);

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const [s, h] = await Promise.all([getAdminStats(), getAdminHealth()]);
      setStats(s);
      setHealth(h);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setOverviewError(errMessage(err));
      setStats(null);
      setHealth(null);
    } finally {
      setOverviewLoading(false);
    }
  }, [handleUnauthorized]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const res = await listAdminUsers({
        limit: PAGE_SIZE,
        offset: usersOffset,
        search: userSearch || undefined,
      });
      setUsers(res.users);
      setUsersTotal(res.total);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setUsersError(errMessage(err));
      setUsers([]);
      setUsersTotal(0);
    } finally {
      setUsersLoading(false);
    }
  }, [handleUnauthorized, userSearch, usersOffset]);

  const loadJobs = useCallback(async () => {
    setJobsLoading(true);
    setJobsError(null);
    try {
      const res = await listAdminJobs({
        limit: PAGE_SIZE,
        offset: jobsOffset,
        status: jobStatus || undefined,
        type: jobType || undefined,
      });
      setJobs(res.jobs);
      setJobsTotal(res.total);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setJobsError(errMessage(err));
      setJobs([]);
      setJobsTotal(0);
    } finally {
      setJobsLoading(false);
    }
  }, [handleUnauthorized, jobStatus, jobType, jobsOffset]);

  useEffect(() => {
    void getCapabilities()
      .then((c) => setHosted(c.hosted === true))
      .catch(() => setHosted(false));
  }, []);

  useEffect(() => {
    if (hosted && activeTab === 'billing') setActiveTab('overview');
  }, [hosted, activeTab]);

  useEffect(() => {
    if (!authed) return;
    if (activeTab === 'overview') void loadOverview();
  }, [authed, activeTab, loadOverview]);

  useEffect(() => {
    if (!authed) return;
    if (activeTab === 'users') void loadUsers();
  }, [authed, activeTab, loadUsers]);

  useEffect(() => {
    if (!authed) return;
    if (activeTab === 'jobs') void loadJobs();
  }, [authed, activeTab, loadJobs]);

  if (!authed) {
    return <AdminLoginGate onAuthed={() => setAuthed(true)} />;
  }

  const onDeleteUser = async (userId: string) => {
    if (!window.confirm('Delete this user and all their keys, jobs, and usage?')) return;
    setActionError(null);
    try {
      await deleteAdminUser(userId);
      await loadUsers();
      if (activeTab === 'overview') await loadOverview();
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setActionError(errMessage(err));
    }
  };

  const onDeleteJob = async (jobId: string) => {
    if (!window.confirm('Delete this job and its results?')) return;
    setActionError(null);
    try {
      await deleteAdminJob(jobId);
      await loadJobs();
      if (activeTab === 'overview') await loadOverview();
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setActionError(errMessage(err));
    }
  };

  const logoutAdmin = () => {
    setAdminToken('');
    setAuthed(false);
  };

  const nav = [
    { id: 'overview' as const, label: 'System Health', icon: Activity },
    { id: 'users' as const, label: 'User Management', icon: Users },
    { id: 'jobs' as const, label: 'Jobs', icon: Briefcase },
    // Financials stub is for self-host operators (billing APIs are HOSTED_MODE-only).
    ...(!hosted
      ? [{ id: 'billing' as const, label: 'Financials', icon: CreditCard }]
      : []),
    { id: 'settings' as const, label: 'Admin Settings', icon: Settings },
  ];

  const statCards = stats
    ? [
        {
          label: 'Total Users',
          value: String(stats.total_users),
          status: 'neutral' as const,
          icon: Users,
        },
        {
          label: 'Requests (30d)',
          value: stats.total_requests_30d.toLocaleString(),
          status: 'neutral' as const,
          icon: Zap,
        },
        {
          label: 'Success Rate',
          value: `${stats.success_rate}%`,
          status: stats.success_rate >= 95 ? ('success' as const) : ('warning' as const),
          icon: CheckCircle2,
        },
        {
          label: 'Active Jobs',
          value: String(stats.active_jobs),
          status: stats.failed_jobs > 0 ? ('warning' as const) : ('success' as const),
          icon: Server,
        },
      ]
    : [];

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-[#111827] flex flex-col font-sans antialiased">
      <header className="h-14 border-b bg-white flex items-center justify-between px-6 sticky top-0 z-50">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="bg-black p-1.5 rounded-md">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <span className="font-bold tracking-tight text-sm uppercase">FireScrapling Admin</span>
          </div>
          {activeTab === 'users' && (
            <form
              className="relative w-96"
              onSubmit={(e) => {
                e.preventDefault();
                setUsersOffset(0);
                setUserSearch(userSearchInput.trim());
              }}
            >
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-gray-400" />
              <Input
                value={userSearchInput}
                onChange={(e) => setUserSearchInput(e.target.value)}
                placeholder="Search users by email…"
                className="h-9 pl-9 bg-gray-50 border-gray-200 text-xs focus:ring-1 focus:ring-black rounded-md"
              />
            </form>
          )}
        </div>
        <div className="flex items-center gap-3">
          {health && (
            <Badge
              variant="outline"
              className={cn(
                'text-[9px] font-black uppercase tracking-wider',
                health.db === 'ok' ? 'border-green-200 text-green-700 bg-green-50' : 'border-red-200 text-red-600',
              )}
            >
              DB {health.db} · {health.active_sessions} sessions
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[10px] font-bold uppercase border-gray-200"
            onClick={logoutAdmin}
          >
            Clear Token
          </Button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-56 border-r bg-white flex flex-col">
          <nav className="p-3 space-y-1">
            {nav.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-semibold transition-colors',
                  activeTab === item.id
                    ? 'bg-gray-100 text-black'
                    : 'text-gray-500 hover:bg-gray-50 hover:text-black',
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </aside>

        <ScrollArea className="flex-1">
          <div className="p-8 space-y-6 max-w-[1600px] mx-auto">
            {actionError && (
              <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                {actionError}
              </div>
            )}

            {activeTab === 'overview' && (
              <>
                {overviewLoading && (
                  <div className="flex items-center gap-2 text-xs text-gray-500 font-semibold">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading platform stats…
                  </div>
                )}
                {overviewError && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700 flex items-center justify-between">
                    <span>{overviewError}</span>
                    <Button size="sm" variant="outline" className="h-7 text-[10px]" onClick={() => void loadOverview()}>
                      Retry
                    </Button>
                  </div>
                )}
                {!overviewLoading && !overviewError && stats && (
                  <>
                    <div className="flex items-center justify-between">
                      <h2 className="text-sm font-bold uppercase tracking-widest text-gray-500">Platform Overview</h2>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 text-[10px] font-bold uppercase border-gray-200"
                        onClick={() => void loadOverview()}
                      >
                        <RefreshCcw className="h-3 w-3 mr-1.5" /> Refresh
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      {statCards.map((stat) => (
                        <Card key={stat.label} className="shadow-none border-gray-200 rounded-lg">
                          <CardContent className="p-4 flex items-center justify-between">
                            <div className="space-y-1">
                              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{stat.label}</p>
                              <div className="flex items-center gap-2">
                                <span className="text-xl font-bold tracking-tight">{stat.value}</span>
                                {stat.status === 'success' && <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />}
                                {stat.status === 'warning' && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                              </div>
                            </div>
                            <div className="p-2 bg-gray-50 rounded-md">
                              <stat.icon className="h-4 w-4 text-gray-400" />
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <Card className="shadow-none border-gray-200 rounded-lg">
                        <CardHeader className="p-4 pb-0">
                          <CardTitle className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                            Failed Jobs
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 pt-1">
                          <div className="text-2xl font-bold tracking-tight">{stats.failed_jobs}</div>
                        </CardContent>
                      </Card>
                      <Card className="shadow-none border-gray-200 rounded-lg">
                        <CardHeader className="p-4 pb-0">
                          <CardTitle className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                            Avg Latency (30d)
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 pt-1">
                          <div className="text-2xl font-bold tracking-tight">{stats.avg_latency_ms} ms</div>
                        </CardContent>
                      </Card>
                      <Card className="shadow-none border-gray-200 rounded-lg">
                        <CardHeader className="p-4 pb-0">
                          <CardTitle className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                            Active Sessions
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 pt-1">
                          <div className="text-2xl font-bold tracking-tight">{health?.active_sessions ?? '—'}</div>
                        </CardContent>
                      </Card>
                    </div>
                  </>
                )}
              </>
            )}

            {activeTab === 'users' && (
              <Card className="shadow-none border-gray-200 rounded-lg overflow-hidden bg-white">
                <CardHeader className="p-6 border-b border-gray-100 flex flex-row items-center justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-sm font-bold flex items-center gap-2">
                      <Users className="h-4 w-4" /> USER MANAGEMENT
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {usersTotal} user{usersTotal === 1 ? '' : 's'} total
                      {userSearch ? ` · filtered by “${userSearch}”` : ''}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-[10px] font-bold uppercase border-gray-200"
                    onClick={() => void loadUsers()}
                  >
                    <RefreshCcw className="h-3 w-3 mr-1.5" /> Refresh
                  </Button>
                </CardHeader>
                {usersLoading && (
                  <div className="p-8 flex items-center gap-2 text-xs text-gray-500 font-semibold">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading users…
                  </div>
                )}
                {usersError && (
                  <div className="m-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                    {usersError}
                  </div>
                )}
                {!usersLoading && !usersError && users.length === 0 && (
                  <div className="p-12 text-center text-xs font-semibold text-gray-400 uppercase tracking-widest">
                    No users found
                  </div>
                )}
                {!usersLoading && !usersError && users.length > 0 && (
                  <>
                    <Table>
                      <TableHeader className="bg-gray-50">
                        <TableRow>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">User ID</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Email</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-center">Keys</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-center">Jobs</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-center">Reqs (30d)</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Joined</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {users.map((user) => (
                          <TableRow key={user.id} className="hover:bg-gray-50/50">
                            <TableCell className="font-mono text-[10px] font-semibold text-gray-500">
                              {truncate(user.id, 12)}
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-col">
                                <span className="text-xs font-bold">{user.email}</span>
                                {user.full_name && (
                                  <span className="text-[10px] text-gray-400">{user.full_name}</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-center text-xs font-semibold">{user.key_count}</TableCell>
                            <TableCell className="text-center text-xs font-semibold">{user.job_count}</TableCell>
                            <TableCell className="text-center text-xs font-semibold">{user.request_count_30d}</TableCell>
                            <TableCell className="text-[10px] font-semibold text-gray-500">
                              {formatDate(user.created_at)}
                            </TableCell>
                            <TableCell className="text-right">
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" className="h-8 w-8 p-0 hover:bg-gray-100">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-48 bg-white border-gray-200">
                                  <DropdownMenuLabel className="text-[10px] font-bold uppercase text-gray-400">
                                    Account Actions
                                  </DropdownMenuLabel>
                                  <DropdownMenuSeparator className="bg-gray-100" />
                                  <DropdownMenuItem
                                    className="text-xs font-semibold text-red-600 flex gap-2 focus:bg-red-50 focus:text-red-600"
                                    onClick={() => void onDeleteUser(user.id)}
                                  >
                                    <Trash2 className="h-3.5 w-3.5" /> Delete User
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <div className="flex items-center justify-between px-6 py-3 border-t border-gray-100">
                      <span className="text-[10px] font-semibold text-gray-400">
                        Showing {usersOffset + 1}–{Math.min(usersOffset + PAGE_SIZE, usersTotal)} of {usersTotal}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[10px]"
                          disabled={usersOffset === 0}
                          onClick={() => setUsersOffset((o) => Math.max(0, o - PAGE_SIZE))}
                        >
                          Prev
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[10px]"
                          disabled={usersOffset + PAGE_SIZE >= usersTotal}
                          onClick={() => setUsersOffset((o) => o + PAGE_SIZE)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </Card>
            )}

            {activeTab === 'jobs' && (
              <Card className="shadow-none border-gray-200 rounded-lg overflow-hidden bg-white">
                <CardHeader className="p-6 border-b border-gray-100 space-y-4">
                  <div className="flex flex-row items-center justify-between">
                    <div className="space-y-1">
                      <CardTitle className="text-sm font-bold flex items-center gap-2">
                        <Briefcase className="h-4 w-4" /> PLATFORM JOBS
                      </CardTitle>
                      <CardDescription className="text-xs">
                        {jobsTotal} job{jobsTotal === 1 ? '' : 's'} total
                      </CardDescription>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-[10px] font-bold uppercase border-gray-200"
                      onClick={() => void loadJobs()}
                    >
                      <RefreshCcw className="h-3 w-3 mr-1.5" /> Refresh
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <select
                      value={jobStatus}
                      onChange={(e) => {
                        setJobsOffset(0);
                        setJobStatus(e.target.value);
                      }}
                      className="h-8 text-[10px] font-bold uppercase border border-gray-200 rounded-md px-2 bg-white"
                    >
                      <option value="">All statuses</option>
                      <option value="queued">Queued</option>
                      <option value="running">Running</option>
                      <option value="completed">Completed</option>
                      <option value="failed">Failed</option>
                    </select>
                    <select
                      value={jobType}
                      onChange={(e) => {
                        setJobsOffset(0);
                        setJobType(e.target.value);
                      }}
                      className="h-8 text-[10px] font-bold uppercase border border-gray-200 rounded-md px-2 bg-white"
                    >
                      <option value="">All types</option>
                      <option value="scrape">Scrape</option>
                      <option value="crawl">Crawl</option>
                    </select>
                  </div>
                </CardHeader>
                {jobsLoading && (
                  <div className="p-8 flex items-center gap-2 text-xs text-gray-500 font-semibold">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading jobs…
                  </div>
                )}
                {jobsError && (
                  <div className="m-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                    {jobsError}
                  </div>
                )}
                {!jobsLoading && !jobsError && jobs.length === 0 && (
                  <div className="p-12 text-center text-xs font-semibold text-gray-400 uppercase tracking-widest">
                    No jobs found
                  </div>
                )}
                {!jobsLoading && !jobsError && jobs.length > 0 && (
                  <>
                    <Table>
                      <TableHeader className="bg-gray-50">
                        <TableRow>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Job ID</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">User</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Type</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Status</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">URL</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Created</TableHead>
                          <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {jobs.map((job) => (
                          <TableRow key={job.id} className="hover:bg-gray-50/50">
                            <TableCell className="font-mono text-[10px] font-semibold text-gray-500">
                              {truncate(job.id, 12)}
                            </TableCell>
                            <TableCell className="text-xs font-semibold">{job.user_email ?? '—'}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className="text-[9px] font-black uppercase">
                                {job.type}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge
                                className={cn(
                                  'text-[9px] font-black uppercase py-0 h-4',
                                  job.status === 'completed' && 'bg-green-500/10 text-green-700',
                                  job.status === 'failed' && 'bg-red-500/10 text-red-600',
                                  (job.status === 'running' || job.status === 'queued') &&
                                    'bg-amber-500/10 text-amber-700',
                                )}
                              >
                                {job.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-[10px] font-mono text-gray-500 max-w-[220px] truncate" title={job.url}>
                              {job.url}
                            </TableCell>
                            <TableCell className="text-[10px] font-semibold text-gray-500">
                              {formatDate(job.created_at)}
                            </TableCell>
                            <TableCell className="text-right">
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" className="h-8 w-8 p-0 hover:bg-gray-100">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-48 bg-white border-gray-200">
                                  <DropdownMenuLabel className="text-[10px] font-bold uppercase text-gray-400">
                                    Job Actions
                                  </DropdownMenuLabel>
                                  <DropdownMenuSeparator className="bg-gray-100" />
                                  <DropdownMenuItem
                                    className="text-xs font-semibold text-red-600 flex gap-2 focus:bg-red-50 focus:text-red-600"
                                    onClick={() => void onDeleteJob(job.id)}
                                  >
                                    <Trash2 className="h-3.5 w-3.5" /> Delete Job
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <div className="flex items-center justify-between px-6 py-3 border-t border-gray-100">
                      <span className="text-[10px] font-semibold text-gray-400">
                        Showing {jobsOffset + 1}–{Math.min(jobsOffset + PAGE_SIZE, jobsTotal)} of {jobsTotal}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[10px]"
                          disabled={jobsOffset === 0}
                          onClick={() => setJobsOffset((o) => Math.max(0, o - PAGE_SIZE))}
                        >
                          Prev
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[10px]"
                          disabled={jobsOffset + PAGE_SIZE >= jobsTotal}
                          onClick={() => setJobsOffset((o) => o + PAGE_SIZE)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </Card>
            )}

            {!hosted && activeTab === 'billing' && (
              <Card className="shadow-none border-gray-200 rounded-lg bg-white">
                <CardContent className="p-12 text-center space-y-3">
                  <div className="inline-flex p-4 rounded-full bg-gray-50 border border-gray-100">
                    <CreditCard className="h-8 w-8 text-gray-300" />
                  </div>
                  <h3 className="text-sm font-bold uppercase tracking-widest">Financials</h3>
                  <p className="text-xs text-gray-400 font-medium max-w-sm mx-auto">
                    Billing and plan management are available when{' '}
                    <code className="text-[10px] bg-gray-100 px-1 rounded">HOSTED_MODE=true</code>.
                    This instance is running self-hosted.
                  </p>
                </CardContent>
              </Card>
            )}

            {activeTab === 'settings' && (
              <Card className="shadow-none border-gray-200 rounded-lg bg-white">
                <CardContent className="p-12 text-center space-y-3">
                  <div className="inline-flex p-4 rounded-full bg-gray-50 border border-gray-100">
                    <Settings className="h-8 w-8 text-gray-300" />
                  </div>
                  <h3 className="text-sm font-bold uppercase tracking-widest">Admin Settings</h3>
                  <p className="text-xs text-gray-400 font-medium max-w-sm mx-auto">
                    Admin access is controlled by{' '}
                    <code className="text-[10px] bg-gray-100 px-1 rounded">ADMIN_SECRET</code>.
                    There is no additional settings panel in this console yet.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
