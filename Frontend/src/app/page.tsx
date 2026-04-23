"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { RegisterSchema, RegisterInput } from "@/lib/schema";
import axios from "axios";
import toast, { Toaster } from "react-hot-toast";

export default function RegisterPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterInput>({
    resolver: zodResolver(RegisterSchema),
  });

  const onSubmit = async (data: RegisterInput) => {
    try {
      // Backend request
      const response = await axios.post("http://localhost:8000/register", data);
      
      if (response.status === 200) {
        toast.success(response.data.message || "Registration Successful!");
      }
    } catch (error: any) {
      console.error("Submission Error:", error);

      // 1. Agar backend ne specific error message bheja (400, 404, etc.)
      if (error.response && error.response.data && error.response.data.detail) {
        toast.error(error.response.data.detail);
      } 
      // 2. Agar backend connection hi nahi ho pa raha (Network Error)
      else if (error.request) {
        toast.error("Cannot connect to server. Is your Python backend running?");
      } 
      // 3. Koi aur masla
      else {
        toast.error("An unexpected error occurred.");
      }
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Toaster position="top-center" />
      <div className="w-full max-w-md bg-white p-8 rounded-xl shadow-lg">
        <h1 className="text-2xl font-bold text-gray-800 mb-6 text-center">
          Automate Your Email Campaigns
        </h1>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Full Name</label>
            <input
              {...register("name")}
              className="text-gray-900 mt-1 block w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Full name here"
            />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Email Address</label>
            <input
              {...register("email")}
              className="text-gray-900 mt-1 block w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="email@example.com"
            />
            {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Phone Number</label>
            <input
              {...register("phone")}
              className="text-gray-900 mt-1 block w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="03XXXXXXXXX"
            />
            {errors.phone && <p className="text-red-500 text-xs mt-1">{errors.phone.message}</p>}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-300 disabled:bg-gray-400"
          >
            {isSubmitting ? "Processing..." : "Submit"}
          </button>
        </form>
      </div>
    </main>
  );
}