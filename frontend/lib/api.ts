/**
 * API Client for Deforestation Monitoring Backend
 */

import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export const apiClient = axios.create({
    baseURL: `${API_URL}/api`,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 30000,
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
    }
);

export interface Alert {
    id: number;
    detection_date: string;
    confidence_score: number;
    area_hectares: number;
    centroid_lat: number;
    centroid_lon: number;
    risk_tier: 'TIER_1' | 'TIER_2';
    status: 'PENDING' | 'VERIFIED' | 'FALSE_POSITIVE' | 'INVESTIGATING';
    alt_vv_drop_db: number;
    alt_vh_drop_db: number;
    boundary_name?: string;
    boundary_type?: string;
}

export interface AlertFeatureCollection {
    type: 'FeatureCollection';
    features: Array<{
        type: 'Feature';
        id: number;
        properties: Alert;
        geometry: GeoJSON.Geometry;
    }>;
    metadata: {
        total: number;
        limit: number;
        offset: number;
    };
}

export interface AlertStats {
    total_alerts: number;
    tier2_alerts: number;
    verified_alerts: number;
    false_positives: number;
    total_area_hectares: number;
    alerts_last_7_days: number;
    alerts_last_30_days: number;
}

export interface TimeSeriesObservation {
    date: string;
    vv: {
        mean: number;
        std: number;
        median: number;
        min: number;
        max: number;
    };
    vh: {
        mean: number;
        std: number;
        median: number;
        min: number;
        max: number;
    };
    pixel_count: number;
    source: string;
}

export interface BackscatterProfile {
    grid_cell_id: string;
    profile: Array<{
        date: string;
        vv_db: number;
        vh_db: number;
    }>;
    count: number;
}

// ============================================================================
// API Methods
// ============================================================================

export const api = {
    // Alerts
    async getAlerts(params?: {
        status?: string;
        risk_tier?: string;
        limit?: number;
        offset?: number;
    }): Promise<AlertFeatureCollection> {
        const response = await apiClient.get('/alerts', { params });
        return response.data;
    },

    async getBoundaries(type?: string): Promise<any> {
        const response = await apiClient.get('/boundaries', { params: { type } });
        return response.data;
    },

    async getAlertById(id: number): Promise<Alert> {
        const response = await apiClient.get(`/alerts/${id}`);
        return response.data;
    },

    async updateAlertStatus(
        id: number,
        status: string,
        notes?: string,
        verified_by?: string
    ): Promise<Alert> {
        const response = await apiClient.put(`/alerts/${id}/status`, {
            status,
            notes,
            verified_by,
        });
        return response.data.alert;
    },

    async getAlertStats(): Promise<AlertStats> {
        const response = await apiClient.get('/alerts/stats');
        return response.data;
    },

    // Time Series
    async getTimeSeries(gridId: string, days: number = 180): Promise<TimeSeriesObservation[]> {
        const response = await apiClient.get(`/timeseries/${gridId}`, {
            params: { days },
        });
        return response.data.observations;
    },

    async getBackscatterProfile(gridId: string): Promise<BackscatterProfile> {
        const response = await apiClient.get(`/timeseries/${gridId}/profile`);
        return response.data;
    },

    // Health Check
    async healthCheck(): Promise<{ status: string; timestamp: string }> {
        const response = await apiClient.get('/health');
        return response.data;
    },
};

export default api;
