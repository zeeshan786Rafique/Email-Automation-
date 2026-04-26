"use client";
import { useEffect, useState } from "react";
import axios from "axios";

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await axios.get("http://localhost:8000/stats");
        // 🔍 Console check: Is se aap Inspect Element > Console mein 
        // dekh sakte hain ke backend se 'Email' aa raha hai ya kuch aur.
        console.log("Backend Data:", res.data.data[0]); 
        setStats(res.data);
      } catch (err) {
        console.error("Fetch Error:", err);
      }
    };
    fetchStats();
  }, []);

  if (!stats) return <div className="p-10 text-center">Loading Dashboard...</div>;

  // Safe Search logic
  const filteredData = stats.data.filter((user: any) => {
    const userName = (user.Name || user.name || "").toLowerCase();
    const userEmail = (user.Email || user.email || "").toLowerCase();
    const search = searchTerm.toLowerCase();
    return userName.includes(search) || userEmail.includes(search);
  });

  return (
    <div className="p-8 bg-gray-100 min-h-screen">
      <h1 className="text-3xl font-bold mb-8 text-gray-800 text-center">Admin Control Center</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
          <p className="text-sm text-gray-500 font-bold uppercase">Total Registrations</p>
          <h2 className="text-3xl font-bold">{stats.total}</h2>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
          <p className="text-sm text-gray-500 font-bold uppercase">Hot Leads / Replied</p>
          <h2 className="text-3xl font-bold">{stats.replied}</h2>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-yellow-500">
          <p className="text-sm text-gray-500 font-bold uppercase">Pending / Follow-ups</p>
          <h2 className="text-3xl font-bold">{stats.pending}</h2>
        </div>
      </div>

      {/* Search & Table */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <input
          type="text"
          placeholder="Search by name or email..."
          className="w-full p-2 border border-gray-300 rounded-md mb-6 text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none"
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b bg-gray-50 text-gray-700">
                <th className="p-3">Name</th>
                <th className="p-3">Email</th>
                <th className="p-3">Phone</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map((user: any, index: number) => (
                <tr key={index} className="border-b hover:bg-gray-50 text-gray-600 transition-colors">
                  <td className="p-3 font-medium">{user.Name || user.name || "N/A"}</td>
                  <td className="p-3">{user.Email || user.email || "N/A"}</td>
                  <td className="p-3">{user.Phone || user.phone || "N/A"}</td>
                  <td className="p-3">
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                      user.Status === 'Hot Lead' ? 'bg-green-100 text-green-700' : 
                      user.Status === 'Cold Lead' ? 'bg-red-100 text-red-700' : 
                      user.Status === 'Follow-up' ? 'bg-yellow-100 text-yellow-700' : 
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {user.Status || "Not Replied"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}