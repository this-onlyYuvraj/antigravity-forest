'use client';

import { useState, useEffect } from 'react';
import { X, AlertTriangle, Bell } from 'lucide-react';

export interface Notification {
    id: string;
    type: 'success' | 'warning' | 'error' | 'info';
    title: string;
    message: string;
    timestamp: Date;
}

interface NotificationCenterProps {
    notifications: Notification[];
    onDismiss: (id: string) => void;
}

export function NotificationCenter({ notifications, onDismiss }: NotificationCenterProps) {
    const [visible, setVisible] = useState<string[]>([]);

    useEffect(() => {
        // Show new notifications
        notifications.forEach(notif => {
            if (!visible.includes(notif.id)) {
                setVisible(prev => [...prev, notif.id]);

                // Auto-dismiss after 10 seconds
                setTimeout(() => {
                    handleDismiss(notif.id);
                }, 10000);
            }
        });
    }, [notifications]);

    const handleDismiss = (id: string) => {
        setVisible(prev => prev.filter(v => v !== id));
        setTimeout(() => onDismiss(id), 300); // Wait for animation
    };

    const getIcon = (type: string) => {
        switch (type) {
            case 'warning':
            case 'error':
                return <AlertTriangle className="w-5 h-5" />;
            default:
                return <Bell className="w-5 h-5" />;
        }
    };

    const getColors = (type: string) => {
        switch (type) {
            case 'success':
                return 'from-emerald-500 to-teal-600 border-emerald-500/30';
            case 'warning':
                return 'from-yellow-500 to-orange-600 border-yellow-500/30';
            case 'error':
                return 'from-red-500 to-rose-600 border-red-500/30';
            default:
                return 'from-blue-500 to-cyan-600 border-blue-500/30';
        }
    };

    return (
        <div className="fixed top-4 right-4 z-[9999] space-y-3 max-w-md">
            {notifications.map(notif => (
                <div
                    key={notif.id}
                    className={`notification-${visible.includes(notif.id) ? 'enter' : 'exit'} 
                      bg-slate-900/95 backdrop-blur-xl border rounded-xl shadow-2xl overflow-hidden
                      ${getColors(notif.type)}`}
                >
                    <div className="flex items-start gap-3 p-4">
                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${getColors(notif.type)} 
                            flex items-center justify-center text-white flex-shrink-0`}>
                            {getIcon(notif.type)}
                        </div>

                        <div className="flex-1 min-w-0">
                            <h4 className="text-white font-semibold text-sm">
                                {notif.title}
                            </h4>
                            <p className="text-gray-300 text-sm mt-1 break-words">
                                {notif.message}
                            </p>
                            <p className="text-gray-500 text-xs mt-2">
                                {notif.timestamp.toLocaleTimeString()}
                            </p>
                        </div>

                        <button
                            onClick={() => handleDismiss(notif.id)}
                            className="text-gray-400 hover:text-white transition-colors flex-shrink-0"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

// Hook to manage notifications
export function useNotifications() {
    const [notifications, setNotifications] = useState<Notification[]>([]);

    const addNotification = (
        type: Notification['type'],
        title: string,
        message: string
    ) => {
        const notification: Notification = {
            id: `${Date.now()}-${Math.random()}`,
            type,
            title,
            message,
            timestamp: new Date(),
        };

        setNotifications(prev => [...prev, notification]);
    };

    const dismissNotification = (id: string) => {
        setNotifications(prev => prev.filter(n => n.id !== id));
    };

    const clearAll = () => {
        setNotifications([]);
    };

    return {
        notifications,
        addNotification,
        dismissNotification,
        clearAll,
    };
}
