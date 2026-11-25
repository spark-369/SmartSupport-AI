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
import { registerSchema, type RegisterValues } from '@/lib/validation'
import { useAuthStore } from '@/stores/authStore'

export default function RegisterPage() {
  const navigate = useNavigate()
  const register = useAuthStore((s) => s.register)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { full_name: '', email: '', password: '', confirm: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitting(true)
    try {
      await register(values.full_name, values.email, values.password)
      toast.success('Welcome aboard', { description: 'Your account is ready.' })
      navigate('/')
    } catch (error) {
      toast.error('Registration failed', { description: (error as Error).message })
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
            Create <span className="italic text-primary">account</span>
          </h1>
          <p className="micro-label mt-2">Join the support desk</p>
        </div>

        <Card className="shadow-2xl">
          <CardContent className="pt-5">
            <Form {...form}>
              <form onSubmit={onSubmit} className="grid gap-4">
                <FormField
                  control={form.control}
                  name="full_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Full name</FormLabel>
                      <FormControl>
                        <Input placeholder="Ada Lovelace" autoComplete="name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
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
                <div className="grid grid-cols-2 gap-3">
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Password</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="8+ chars" autoComplete="new-password" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="confirm"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Confirm</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="repeat" autoComplete="new-password" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <Button type="submit" size="lg" disabled={submitting}>
                  {submitting && <Loader2 className="size-4 animate-spin" />}
                  Create account
                </Button>
              </form>
            </Form>
            <p className="mt-4 text-center text-sm text-muted-foreground">
              Already registered?{' '}
              <Link to="/login" className="text-primary underline-offset-4 hover:underline">
                Sign in
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
