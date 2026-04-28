"use client";
import { useEffect, useState } from "react";
import axios from "axios";

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);

  // Sahi Base URL (Bagair aakhir wale slash ke)
  const API_URL = "https://emailautomation-tau.vercel.app";

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_URL}/stats`);
      console.log("Full Backend Response:", res.data); // Inspect Console mein check karne ke liye
      setStats(res.data);
    } catch (err) {
      console.error("Fetch Error:", err);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleCheckReplies = async () => {
    setLoading(true);
    try {
      alert("Gmail check ho raha hai... is mein 10-15 seconds lag sakte hain.");
      const res = await axios.get(`${API_URL}/check-replies`);
      alert(res.data.message || "Replies check ho gayeen!");
      await fetchStats(); // Stats refresh karein
    } catch (err) {
      console.error("Error checking replies:", err);
      alert("Replies check karne mein masla aya.");
    } finally {
      setLoading(false);
    }
  };

  if (!stats) return <div className="p-10 text-center">Loading Dashboard...</div>;

  // Safe Search logic
  const filteredData = stats.data?.filter((user: any) => {
    const userName = (user.Name || user.name || "").toLowerCase();
    const userEmail = (user.Email || user.email || "").toLowerCase();
    const search = searchTerm.toLowerCase();
    return userName.includes(search) || userEmail.includes(search);
  }) || [];

  return (
    <div className="p-8 bg-gray-100 min-h-screen">
      <h1 className="text-3xl font-bold mb-8 text-gray-800 text-center">Admin Control Center</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
          <p className="text-sm text-black font-bold uppercase">Total Registrations</p>
          <h2 className="text-3xl text-black font-bold">{stats.total || 0}</h2>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
          <p className="text-sm text-black font-bold uppercase">Hot Leads / Replied</p>
          {/* Backend key match: hot_leads */}
          <h2 className="text-3xl font-bold text-black">{stats.hot_leads || 0}</h2>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-yellow-500">
          <p className="text-sm text-black font-bold uppercase">Pending / Follow-ups</p>
          {/* Backend key match: pending_followups */}
          <h2 className="text-3xl font-bold text-black">{stats.pending_followups || 0}</h2>
        </div>
      </div>

      {/* Search & Action Button */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex flex-col md:flex-row justify-between gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by name or email..."
            className="flex-1 p-2 border border-gray-300 rounded-md text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none"
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          
          <button 
            onClick={handleCheckReplies}
            disabled={loading}
            className={`${
              loading ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
            } text-white px-6 py-2 rounded-md font-bold transition flex items-center justify-center`}
          >
            {loading ? "Checking..." : "Check New Replies 🔄"}
          </button>
        </div>

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
                      (user.Status === 'Replied' || user.Status === 'Hot Lead') ? 'bg-green-100 text-green-700' : 
                      user.Status === 'Cold Lead' ? 'bg-red-100 text-red-700' : 
                      (user.Status === 'Not Replied' || user.Status === 'Follow-up') ? 'bg-yellow-100 text-yellow-700' : 
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