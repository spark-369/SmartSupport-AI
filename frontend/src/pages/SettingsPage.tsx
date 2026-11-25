import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { KeyRound, Loader2, Save, ShieldCheck, UserRound } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { passwordSchema, profileSchema, type PasswordValues, type ProfileValues } from '@/lib/validation'
import { useAuthStore } from '@/stores/authStore'
import { useChangePassword, useUpdateMe } from '@/hooks/queries'

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user)

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-border bg-card/40 px-8 py-6 backdrop-blur">
        <div className="mx-auto max-w-3xl">
          <p className="micro-label">Account</p>
          <h1 className="mt-1 font-display text-3xl">
            Workspace <span className="italic text-primary">settings</span>
          </h1>
        </div>
      </header>

      <div className="mx-auto max-w-3xl space-y-6 px-8 py-8">
        <ProfileCard />
        <PasswordCard />

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldCheck className="size-4 text-primary" /> Session
            </CardTitle>
            <CardDescription>Security posture of this account.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">Email</span>
              <span className="font-mono text-xs">{user?.email}</span>
            </div>
            <Separator />
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">Role</span>
              <Badge variant={user?.role === 'admin' ? 'default' : 'secondary'} className="uppercase">
                {user?.role}
              </Badge>
            </div>
            <Separator />
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">Access token</span>
              <span className="font-mono text-xs text-muted-foreground">30 min · rotated refresh cookie</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function ProfileCard() {
  const user = useAuthStore((s) => s.user)
  const updateMe = useUpdateMe()

  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: user?.full_name ?? '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await updateMe.mutateAsync(values)
      toast.success('Profile updated', { description: 'Your display name has been saved.' })
    } catch (error) {
      toast.error('Could not update profile', { description: (error as Error).message })
    }
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <UserRound className="size-4 text-primary" /> Profile
        </CardTitle>
        <CardDescription>How your name appears across the workspace.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={onSubmit} className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <FormField
              control={form.control}
              name="full_name"
              render={({ field }) => (
                <FormItem className="flex-1">
                  <FormLabel>Display name</FormLabel>
                  <FormControl>
                    <Input placeholder="Ada Lovelace" autoComplete="name" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" disabled={updateMe.isPending || !form.formState.isDirty}>
              {updateMe.isPending ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
              Save
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}


function PasswordCard() {
  const changePassword = useChangePassword()
  const [justChanged, setJustChanged] = useState(false)

  const form = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '', confirm: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await changePassword.mutateAsync({
        current_password: values.current_password,
        new_password: values.new_password,
      })
      form.reset()
      setJustChanged(true)
      toast.success('Password changed', {
        description: 'Other devices were signed out; this device was re-authenticated.',
      })
    } catch (error) {
      toast.error('Could not change password', { description: (error as Error).message })
    }
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <KeyRound className="size-4 text-primary" /> Password
        </CardTitle>
        <CardDescription>
          Changing your password signs out every other device immediately.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={onSubmit} className="grid gap-4">
            <FormField
              control={form.control}
              name="current_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="current-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="new_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New password</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="8+ chars, letter + digit"
                        autoComplete="new-password"
                        {...field}
                      />
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
                    <FormLabel>Confirm new password</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={changePassword.isPending}>
                {changePassword.isPending && <Loader2 className="size-4 animate-spin" />}
                Update password
              </Button>
              {justChanged && (
                <span className="font-mono text-[11px] tracking-wide text-success uppercase">
                  rotated · other sessions revoked
                </span>
              )}
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
