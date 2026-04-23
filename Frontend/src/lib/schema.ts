import { z } from "zod";

export const RegisterSchema = z.object({
  name: z.string().min(2, "Name is too short"),
  email: z.string().email("Invalid email address"),
  phone: z.string().min(10, "Phone number must be at least 10 digits"),
});

export type RegisterInput = z.infer<typeof RegisterSchema>;