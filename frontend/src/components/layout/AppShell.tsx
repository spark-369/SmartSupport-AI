import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  BookOpen,
  Bot,
  Inbox,
  LogOut,
  Menu,
  MessageSquare,
  Search,
  Settings,
  Shield,
} from 'lucide-react'
import { toast } from 'sonner'

import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { ErrorBoundary } from '@/components/layout/ErrorBoundary'

interface NavItem {
  to: string
  label: string
  icon: typeof BookOpen
  end: boolean
  adminOnly?: boolean
}

const navigation: NavItem[] = [
  { to: '/', label: 'Products', icon: BookOpen, end: true },
  { to: '/chat', label: 'Support Chat', icon: MessageSquare, end: false },
  { to: '/tickets', label: 'Ticket Triage', icon: Inbox, end: false },
  { to: '/search', label: 'Manual Search', icon: Search, end: false },
  { to: '/insights', label: 'AI Insights', icon: BarChart3, end: false, adminOnly: true },
  { to: '/settings', label: 'Settings', icon: Settings, end: false },
]

interface HealthResponse {
  status: string
  components: Record<string, string>
}

function useSystemHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthResponse>('/health'),
    refetchInterval: 30_000,
    staleTime: 20_000,
    retry: 1,
  })
}

/** Live dependency status: database · redis · ollama. */
function HealthBadge({ compact = false }: { compact?: boolean }) {
  const { data, isError } = useSystemHealth()
  const down = isError
  const ok = !down && data?.status === 'ok'
  const degraded = !down && data?.status === 'degraded'
  const label = down
    ? 'Backend unreachable'
    : ok
      ? 'All systems operational'
      : degraded
        ? `Degraded: ${Object.entries(data?.components ?? {})
            .filter(([, v]) => v !== 'ok')
            .map(([k]) => k)
            .join(', ')} unavailable`
        : 'Checking health…'
  const dot = down ? 'bg-destructive' : ok ? 'bg-success' : degraded ? 'bg-warning' : 'bg-muted-foreground'

  return (
    <div
      className="flex items-center gap-2 rounded-sm border border-border bg-background/60 px-2.5 py-1.5"
      title={label}
    >
      <span className={cn('size-1.5 shrink-0 rounded-full', dot, !down && 'animate-pulse-soft')} />
      {!compact && (
        <span className="micro-label !text-[9px]">
          {down ? 'offline' : ok ? 'online' : degraded ? 'degraded' : '…'}
        </span>
      )}
    </div>
  )
}

function Logo() {
  return (
    <div className="flex size-9 shrink-0 items-center justify-center rounded-sm bg-primary/15 ring-1 ring-primary/30">
      <Bot className="size-5 text-primary" />
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const role = useAuthStore((s) => s.user?.role)
  const items = navigation.filter((item) => !item.adminOnly || role === 'admin')

  return (
    <nav className="flex flex-col gap-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            [
              'flex items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
              isActive
                ? 'bg-primary/10 text-primary ring-1 ring-primary/25'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            ].join(' ')
          }
        >
          <item.icon className="size-4" />
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

function UserMenu({ align = 'start' }: { align?: 'start' | 'end' }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const initials = (user?.full_name ?? '?')
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-3 rounded-sm px-2 py-2 text-left transition-colors hover:bg-accent outline-none focus-visible:ring-2 focus-visible:ring-ring/60">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-accent font-mono text-xs text-foreground ring-1 ring-border">
            {initials}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm">{user?.full_name}</span>
            <span className="micro-label block truncate">{user?.email}</span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className="w-56">
        <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate('/settings')}>
          <Settings className="size-4" /> Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => {
            void logout().then(() => navigate('/login'))
          }}
          className="text-destructive focus:text-destructive"
        >
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function AppShell() {
  const { user, bootstrap } = useAuthStore()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    void bootstrap()
    const onExpired = () => {
      toast.info('Session expired', { description: 'Please sign in again to continue.' })
      navigate('/login')
    }
    window.addEventListener('ss:session-expired', onExpired)
    return () => window.removeEventListener('ss:session-expired', onExpired)
  }, [bootstrap, navigate])

  return (
    <div className="grain flex h-full flex-col">
      {/* Mobile top bar */}
      <header className="flex items-center justify-between gap-3 border-b border-border bg-card/60 px-4 py-2.5 md:hidden">
        <div className="flex min-w-0 items-center gap-2.5">
          <Logo />
          <div className="min-w-0">
            <p className="truncate font-display text-base leading-none">SmartSupport</p>
            <p className="micro-label mt-0.5">AI · RAG v1.0</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <HealthBadge compact />
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Open navigation menu">
                <Menu className="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 gap-0 p-0">
              <SheetHeader className="border-b border-border px-4 py-4">
                <SheetTitle className="flex items-center gap-2.5 text-base">
                  <Logo /> SmartSupport
                </SheetTitle>
                <SheetDescription className="micro-label">workspace navigation</SheetDescription>
              </SheetHeader>
              <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-3">
                <NavItems onNavigate={() => setMenuOpen(false)} />
                {user?.role === 'admin' && (
                  <div className="rounded-sm border border-primary/20 bg-primary/5 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Shield className="size-3.5 text-primary" />
                      <span className="micro-label !text-primary/80">Admin workspace</span>
                    </div>
                  </div>
                )}
              </div>
              <div className="border-t border-border p-3">
                <UserMenu />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Desktop sidebar */}
        <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card/60 md:flex">
          <div className="flex items-center gap-3 px-5 py-5">
            <Logo />
            <div>
              <p className="font-display text-lg leading-none">SmartSupport</p>
              <p className="micro-label mt-1">AI · RAG v1.0</p>
            </div>
          </div>
          <Separator />
          <nav className="flex flex-1 flex-col gap-1 p-3">
            <NavItems />
          </nav>
          <div className="mx-3 mb-3">
            <HealthBadge />
          </div>
          {user?.role === 'admin' && (
            <div className="mx-3 mb-3 rounded-sm border border-primary/20 bg-primary/5 px-3 py-2">
              <div className="flex items-center gap-2">
                <Shield className="size-3.5 text-primary" />
                <span className="micro-label !text-primary/80">Admin workspace</span>
              </div>
            </div>
          )}
          <Separator />
          <div className="p-3">
            <UserMenu />
          </div>
        </aside>

        {/* Main */}
        <main className="relative min-w-0 flex-1 overflow-hidden bg-grid">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
