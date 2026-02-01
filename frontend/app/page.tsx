'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { api, type Alert, type AlertStats } from '@/lib/api';
import { Layers, Map as MapIcon, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import { NotificationCenter, useNotifications } from '@/components/Notifications/NotificationCenter';

// Dynamically import Map to avoid SSR issues with Leaflet
const AlertMap = dynamic(() => import('@/components/Map/AlertMap'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-gray-900 flex items-center justify-center">
    <div className="text-white">Loading map...</div>
  </div>
});

export default function Dashboard() {
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const { notifications, addNotification, dismissNotification } = useNotifications();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await api.getAlertStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
      addNotification('error', 'API Error', 'Failed to load dashboard statistics');
    } finally {
      setLoading(false);
    }
  };

  const handleNewAlert = (alert: Alert) => {
    // Show on-screen notification for new alerts
    const severity = alert.risk_tier === 'TIER_2' ? 'error' : 'warning';
    const title = alert.risk_tier === 'TIER_2'
      ? '🚨 Priority Alert - Protected Area'
      : '⚠️ New Deforestation Detected';

    const message = `Alert #${alert.id} • ${alert.area_hectares.toFixed(2)} ha • ` +
      `Confidence: ${(alert.confidence_score * 100).toFixed(1)}%` +
      (alert.boundary_name ? ` • ${alert.boundary_name}` : '');

    addNotification(severity, title, message);

    // Reload stats to update counters
    loadStats();
  };

  return (
    <div className="flex h-screen w-full bg-slate-950 overflow-hidden text-slate-100">
      <NotificationCenter notifications={notifications} onDismiss={dismissNotification} />

      {/*sidebar*/}
      <aside className="w-80 flex flex-col border-r border-slate-800 bg-slate-900/50 backdrop-blur-md overflow-y-auto">
        {/* Sidebar Header */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-emerald-500 rounded flex items-center justify-center text-lg shadow-lg shadow-emerald-500/20">
              🌲
            </div>
            <h1 className="font-bold text-lg tracking-tight">Forest Monitor</h1>
          </div>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">
            Uttara Kannada, Karnataka
          </p>
        </div>

        {/* Sidebar Content: Dummy Stats Stacking */}
        {!loading && stats && (
          <div className="p-4 space-y-4 flex-1">
            <h2 className="text-xs font-semibold text-slate-500 uppercase px-2 mb-2">Metrics Overview</h2>

            <StatCard
              title="Total Alerts"
              value={stats.total_alerts}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="blue"
              subtitle={`${stats.alerts_last_7_days} in last 7 days`}
            />
            <StatCard
              title="Priority Alerts"
              value={stats.tier2_alerts}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="red"
              subtitle="Protected areas"
            />
            <StatCard
              title="Verified"
              value={stats.verified_alerts}
              icon={<CheckCircle className="w-5 h-5" />}
              color="green"
              subtitle={`${stats.false_positives} false positives`}
            />
            <StatCard
              title="Total Area"
              value={`${stats.total_area_hectares.toFixed(1)} ha`}
              icon={<Clock className="w-5 h-5" />}
              color="purple"
              subtitle="Detected deforestation"
            />
          </div>
        )
        }
      </aside>

      {/*MAP */}
      <main className="flex-1 relative">
        <div className="absolute top-4 right-4 z-[40] flex flex-col gap-2">
          <button className="p-2 bg-slate-900 border border-slate-700 rounded-md shadow-xl hover:bg-slate-800">
            <Layers className="w-5 h-5 text-slate-300" />
          </button>
          <button className="p-2 bg-slate-900 border border-slate-700 rounded-md shadow-xl hover:bg-slate-800">
            <MapIcon className="w-5 h-5 text-slate-300" />
          </button>
        </div>

        <div className="w-full h-full">
          <AlertMap
            onAlertSelect={setSelectedAlert}
            onNewAlert={handleNewAlert}
          />
        </div>
      </main>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: 'blue' | 'red' | 'green' | 'purple';
  subtitle?: string;
}

function StatCard({ title, value, icon, color, subtitle }: StatCardProps) {
  const colors = {
    blue: 'from-blue-500 to-cyan-600',
    red: 'from-red-500 to-rose-600',
    green: 'from-emerald-500 to-teal-600',
    purple: 'from-purple-500 to-violet-600',
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700 hover:border-slate-600 transition-all hover:shadow-lg">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-white mt-2">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${colors[color]} flex items-center justify-center text-white`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
