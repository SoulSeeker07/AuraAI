#!/usr/bin/env python3
"""
TypeScript & JSX AST Parser Performance Benchmark
=================================================
Benchmarks parsing throughput (files/second) and symbol extraction latency
over realistic React / Next.js / TypeScript code patterns.
"""

import time
import sys
from pathlib import Path

# Ensure UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.engineering.language_providers.typescript import TypeScriptLanguageProvider

SAMPLE_TSX_COMPONENT = """
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Avatar } from '@/components/ui/avatar';
import type { UserProfile, AccountSettings, ThemeMode } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { formatCurrency, formatDate } from '@/lib/utils';

export interface DashboardProps {
    initialProfile: UserProfile;
    settings?: AccountSettings;
    onUpdateTheme?: (mode: ThemeMode) => void;
}

export type TabKey = 'overview' | 'analytics' | 'reports' | 'notifications';

export enum NotificationLevel {
    INFO = 'info',
    WARNING = 'warning',
    CRITICAL = 'critical',
}

export const AnalyticsDashboard: React.FC<DashboardProps> = ({
    initialProfile,
    settings,
    onUpdateTheme,
}) => {
    const { user, token, refreshSession } = useAuth();
    const [activeTab, setActiveTab] = useState<TabKey>('overview');
    const [metricCount, setMetricCount] = useState<number>(0);
    const renderCountRef = useRef<number>(0);

    useEffect(() => {
        renderCountRef.current += 1;
        console.log(`[Dashboard] Mounted for user ${user?.id ?? initialProfile.id}`);
        refreshSession();
    }, [user?.id, initialProfile.id, refreshSession]);

    const formattedMetrics = useMemo(() => {
        return {
            totalRevenue: formatCurrency(metricCount * 1250),
            lastSync: formatDate(new Date()),
        };
    }, [metricCount]);

    const handleTabChange = useCallback((newTab: TabKey) => {
        setActiveTab(newTab);
        if (onUpdateTheme && newTab === 'analytics') {
            onUpdateTheme('dark');
        }
    }, [onUpdateTheme]);

    return (
        <Card className="dashboard-container">
            <CardHeader>
                <Avatar src={initialProfile.avatarUrl} alt={initialProfile.username} />
                <h2>Welcome, {initialProfile.username}!</h2>
                <span>Total: {formattedMetrics.totalRevenue}</span>
            </CardHeader>
            <CardContent>
                <div className="tab-bar">
                    <Button onClick={() => handleTabChange('overview')}>Overview</Button>
                    <Button onClick={() => handleTabChange('analytics')}>Analytics</Button>
                    <Button onClick={() => handleTabChange('reports')}>Reports</Button>
                </div>
                <div>Active Tab: {activeTab}</div>
            </CardContent>
        </Card>
    );
};

export default AnalyticsDashboard;
"""

def run_benchmark(iterations: int = 500):
    provider = TypeScriptLanguageProvider()
    
    print("=" * 70)
    print(f"TYPESCRIPT & JSX AST PROVIDER BENCHMARK ({iterations} iterations)")
    print("=" * 70)

    # Warm-up parse
    parsed_warm = provider.parse_file("Dashboard.tsx", SAMPLE_TSX_COMPONENT)
    print(f"Sample File Details:")
    print(f"  • Extracted Symbols: {len(parsed_warm.symbols)}")
    print(f"  • Extracted Imports: {len(parsed_warm.imports)}")
    print(f"  • Extracted Hooks:   {len(parsed_warm.hooks)}")
    print(f"  • JSX Components:    {len(parsed_warm.jsx_elements_used)}")
    print("-" * 70)

    # Timing loop
    start_time = time.perf_counter()
    for i in range(iterations):
        provider.parse_file(f"Component_{i}.tsx", SAMPLE_TSX_COMPONENT)
    elapsed = time.perf_counter() - start_time

    throughput = iterations / elapsed
    ms_per_file = (elapsed / iterations) * 1000.0

    print(f"Results:")
    print(f"  • Total Time:       {elapsed:.4f} seconds")
    print(f"  • Throughput:       {throughput:.1f} files / second")
    print(f"  • Average Latency:  {ms_per_file:.3f} ms / file")
    print("=" * 70)

    assert throughput > 300, f"Throughput {throughput} is lower than expected target (>300 files/sec)"
    print("✅ BENCHMARK PASSED: Ultra-fast in-process TypeScript & JSX parsing verified.")

if __name__ == "__main__":
    run_benchmark(iterations=500)
