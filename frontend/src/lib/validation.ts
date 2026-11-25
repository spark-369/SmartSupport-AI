/** Zod schemas shared by React Hook Form. */

import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

export const registerSchema = z
  .object({
    full_name: z.string().min(2, 'Name must be at least 2 characters').max(120),
    email: z.string().min(1, 'Email is required').email('Enter a valid email'),
    password: z
      .string()
      .min(8, 'Use at least 8 characters')
      .max(128)
      .regex(/[a-zA-Z]/, 'Include at least one letter')
      .regex(/[0-9]/, 'Include at least one digit'),
    confirm: z.string().min(1, 'Confirm your password'),
  })
  .refine((data) => data.password === data.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

export const productSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters').max(160),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'Lowercase letters, digits and dashes only')
    .max(160)
    .optional()
    .or(z.literal('').transform(() => undefined)),
  description: z.string().max(2000).optional().or(z.literal('').transform(() => undefined)),
  version: z.string().max(40).optional().or(z.literal('').transform(() => undefined)),
})

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
export type ProductValues = z.infer<typeof productSchema>
export type ProfileValues = z.infer<typeof profileSchema>
export type PasswordValues = z.infer<typeof passwordSchema>
export type ConversationTitleValues = z.infer<typeof conversationTitleSchema>

export const profileSchema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters').max(120),
})

export const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z
      .string()
      .min(8, 'Use at least 8 characters')
      .max(128)
      .regex(/[a-zA-Z]/, 'Include at least one letter')
      .regex(/[0-9]/, 'Include at least one digit'),
    confirm: z.string().min(1, 'Confirm your new password'),
  })
  .refine((data) => data.new_password === data.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

export const conversationTitleSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, 'Title cannot be empty')
    .max(200, 'Keep the title under 200 characters'),
})
