import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Bot, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { loginSchema, type LoginValues } from '@/lib/validation'
import { useAuthStore } from '@/stores/authStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitting(true)
    try {
      await login(values.email, values.password)
      navigate('/')
    } catch (error) {
      toast.error('Sign in failed', { description: (error as Error).message })
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <div className="grain relative flex h-full items-center justify-center bg-grid p-6">
      <div className="w-full max-w-md animate-rise">
        <div className="mb-8 text-center">
          <div className="mx-auto flex size-14 items-center justify-center rounded-md bg-primary/15 ring-1 ring-primary/30">
            <Bot className="size-7 text-primary" />
          </div>
          <h1 className="mt-4 font-display text-4xl">
            Smart<span className="italic text-primary">Support</span> AI
          </h1>
          <p className="micro-label mt-2">Manual-grounded customer support</p>
        </div>

        <Card className="shadow-2xl">
          <CardContent className="pt-5">
            <Form {...form}>
              <form onSubmit={onSubmit} className="grid gap-4">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="you@company.io" autoComplete="email" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Password</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder="••••••••" autoComplete="current-password" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" size="lg" disabled={submitting}>
                  {submitting && <Loader2 className="size-4 animate-spin" />}
                  Sign in
                </Button>
              </form>
            </Form>
            <p className="mt-4 text-center text-sm text-muted-foreground">
              No account?{' '}
              <Link to="/register" className="text-primary underline-offset-4 hover:underline">
                Create one
              </Link>
            </p>
          </CardContent>
        </Card>

        <p className="mt-6 text-center font-mono text-[11px] text-muted-foreground/60">
          The first registered account becomes the workspace admin.
        </p>
      </div>
    </div>
  )
}
