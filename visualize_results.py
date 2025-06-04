#!/usr/bin/env python3
"""
Visualization and Analysis Tool for Progressive Testing Framework

This script provides comprehensive visualization and analysis capabilities
for interpreting test results and identifying performance bottlenecks.
"""

import json
import csv
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import warnings
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Set style for better-looking plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

class TestResultAnalyzer:
    """Comprehensive analyzer for progressive test results."""
    
    def __init__(self, report_path: str):
        """Initialize analyzer with test report data."""
        self.report_path = Path(report_path)
        self.data = self._load_data()
        self.batch_df = self._create_batch_dataframe()
        
    def _load_data(self) -> Dict[str, Any]:
        """Load test report data from JSON file."""
        if not self.report_path.exists():
            raise FileNotFoundError(f"Report file not found: {self.report_path}")
            
        with open(self.report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _create_batch_dataframe(self) -> pd.DataFrame:
        """Create pandas DataFrame from batch metrics for easier analysis."""
        batch_data = []
        
        for batch in self.data.get('batch_metrics', []):
            batch_data.append({
                'batch_size': batch['batch_size'],
                'total_workflows': batch['total_workflows'],
                'successful_workflows': batch['successful_workflows'],
                'failed_workflows': batch['failed_workflows'],
                'success_rate': batch['success_rate'],
                'avg_execution_time': batch['average_execution_time'],
                'min_execution_time': batch['min_execution_time'],
                'max_execution_time': batch['max_execution_time'],
                'throughput': batch['throughput'],
                'duration': batch['duration'],
                'total_retries': batch['total_retries'],
                'started_at': pd.to_datetime(batch['started_at']),
                'completed_at': pd.to_datetime(batch['completed_at'])
            })
        
        return pd.DataFrame(batch_data)
    
    def plot_performance_metrics(self, output_dir: str = "visualizations") -> List[str]:
        """Generate comprehensive performance metric visualizations."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        generated_files = []
        
        # 1. Throughput vs Batch Size
        plt.figure(figsize=(12, 8))
        plt.subplot(2, 2, 1)
        plt.plot(self.batch_df['batch_size'], self.batch_df['throughput'], 'o-', linewidth=2, markersize=8)
        plt.xlabel('Batch Size')
        plt.ylabel('Throughput (workflows/s)')
        plt.title('Throughput vs Batch Size')
        plt.grid(True, alpha=0.3)
        
        # 2. Execution Time vs Batch Size
        plt.subplot(2, 2, 2)
        plt.plot(self.batch_df['batch_size'], self.batch_df['avg_execution_time'], 'o-', 
                color='orange', linewidth=2, markersize=8, label='Average')
        plt.fill_between(self.batch_df['batch_size'], 
                        self.batch_df['min_execution_time'], 
                        self.batch_df['max_execution_time'], 
                        alpha=0.3, color='orange', label='Min-Max Range')
        plt.xlabel('Batch Size')
        plt.ylabel('Execution Time (s)')
        plt.title('Execution Time vs Batch Size')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 3. Success Rate vs Batch Size
        plt.subplot(2, 2, 3)
        plt.plot(self.batch_df['batch_size'], self.batch_df['success_rate'], 'o-', 
                color='green', linewidth=2, markersize=8)
        plt.xlabel('Batch Size')
        plt.ylabel('Success Rate (%)')
        plt.title('Success Rate vs Batch Size')
        plt.ylim(0, 105)
        plt.grid(True, alpha=0.3)
        
        # 4. Retry Count vs Batch Size
        plt.subplot(2, 2, 4)
        plt.bar(self.batch_df['batch_size'], self.batch_df['total_retries'], 
               color='red', alpha=0.7)
        plt.xlabel('Batch Size')
        plt.ylabel('Total Retries')
        plt.title('Retry Count vs Batch Size')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        performance_file = output_path / f"{self.data['test_name']}_performance_metrics.png"
        plt.savefig(performance_file, dpi=300, bbox_inches='tight')
        plt.close()
        generated_files.append(str(performance_file))
        
        return generated_files
    
    def plot_scalability_analysis(self, output_dir: str = "visualizations") -> List[str]:
        """Generate scalability analysis visualizations."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        generated_files = []
        
        # Scalability Analysis
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. Throughput Efficiency (Throughput per workflow)
        efficiency = self.batch_df['throughput'] / self.batch_df['batch_size']
        ax1.plot(self.batch_df['batch_size'], efficiency, 'o-', linewidth=2, markersize=8)
        ax1.set_xlabel('Batch Size')
        ax1.set_ylabel('Efficiency (throughput/batch_size)')
        ax1.set_title('Throughput Efficiency vs Batch Size')
        ax1.grid(True, alpha=0.3)
        
        # 2. Latency vs Throughput
        ax2.scatter(self.batch_df['throughput'], self.batch_df['avg_execution_time'], 
                   s=self.batch_df['batch_size']*2, alpha=0.7, c=self.batch_df['batch_size'], 
                   cmap='viridis')
        ax2.set_xlabel('Throughput (workflows/s)')
        ax2.set_ylabel('Average Execution Time (s)')
        ax2.set_title('Latency vs Throughput (bubble size = batch size)')
        ax2.grid(True, alpha=0.3)
        
        # 3. Resource Utilization Proxy (Duration vs Expected Duration)
        expected_duration = self.batch_df['batch_size'] / self.batch_df['throughput']
        utilization_ratio = self.batch_df['duration'] / expected_duration
        ax3.plot(self.batch_df['batch_size'], utilization_ratio, 'o-', 
                color='purple', linewidth=2, markersize=8)
        ax3.axhline(y=1.0, color='red', linestyle='--', alpha=0.7, label='Ideal Ratio')
        ax3.set_xlabel('Batch Size')
        ax3.set_ylabel('Actual/Expected Duration Ratio')
        ax3.set_title('Resource Utilization Efficiency')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. Scalability Score
        # Calculate scalability score based on throughput increase vs batch size increase
        scalability_scores = []
        for i in range(1, len(self.batch_df)):
            throughput_ratio = self.batch_df.iloc[i]['throughput'] / self.batch_df.iloc[i-1]['throughput']
            batch_ratio = self.batch_df.iloc[i]['batch_size'] / self.batch_df.iloc[i-1]['batch_size']
            scalability_scores.append(throughput_ratio / batch_ratio)
        
        if scalability_scores:
            ax4.plot(self.batch_df['batch_size'][1:], scalability_scores, 'o-', 
                    color='brown', linewidth=2, markersize=8)
            ax4.axhline(y=1.0, color='red', linestyle='--', alpha=0.7, label='Linear Scaling')
            ax4.set_xlabel('Batch Size')
            ax4.set_ylabel('Scalability Score')
            ax4.set_title('Scalability Score (>1 = super-linear, <1 = sub-linear)')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        scalability_file = output_path / f"{self.data['test_name']}_scalability_analysis.png"
        plt.savefig(scalability_file, dpi=300, bbox_inches='tight')
        plt.close()
        generated_files.append(str(scalability_file))
        
        return generated_files
    
    def detect_anomalies(self) -> Dict[str, Any]:
        """Detect performance anomalies using statistical methods."""
        anomalies = {
            'throughput_anomalies': [],
            'execution_time_anomalies': [],
            'success_rate_anomalies': [],
            'summary': {}
        }
        
        # Z-score based anomaly detection
        z_threshold = 2.0
        
        # Throughput anomalies
        throughput_z = np.abs(stats.zscore(self.batch_df['throughput']))
        throughput_anomalies = self.batch_df[throughput_z > z_threshold]
        for _, row in throughput_anomalies.iterrows():
            anomalies['throughput_anomalies'].append({
                'batch_size': row['batch_size'],
                'value': row['throughput'],
                'z_score': throughput_z[row.name],
                'type': 'outlier'
            })
        
        # Execution time anomalies
        exec_time_z = np.abs(stats.zscore(self.batch_df['avg_execution_time']))
        exec_time_anomalies = self.batch_df[exec_time_z > z_threshold]
        for _, row in exec_time_anomalies.iterrows():
            anomalies['execution_time_anomalies'].append({
                'batch_size': row['batch_size'],
                'value': row['avg_execution_time'],
                'z_score': exec_time_z[row.name],
                'type': 'outlier'
            })
        
        # Success rate anomalies (anything below 95%)
        success_rate_anomalies = self.batch_df[self.batch_df['success_rate'] < 95.0]
        for _, row in success_rate_anomalies.iterrows():
            anomalies['success_rate_anomalies'].append({
                'batch_size': row['batch_size'],
                'value': row['success_rate'],
                'type': 'low_success_rate'
            })
        
        # Summary
        anomalies['summary'] = {
            'total_anomalies': len(anomalies['throughput_anomalies']) + 
                             len(anomalies['execution_time_anomalies']) + 
                             len(anomalies['success_rate_anomalies']),
            'throughput_anomaly_count': len(anomalies['throughput_anomalies']),
            'execution_time_anomaly_count': len(anomalies['execution_time_anomalies']),
            'success_rate_anomaly_count': len(anomalies['success_rate_anomalies'])
        }
        
        return anomalies
    
    def generate_analysis_report(self, output_dir: str = "visualizations") -> str:
        """Generate comprehensive analysis report."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        anomalies = self.detect_anomalies()
        
        # Calculate additional metrics
        max_throughput = self.batch_df['throughput'].max()
        optimal_batch_size = self.batch_df.loc[self.batch_df['throughput'].idxmax(), 'batch_size']
        avg_success_rate = self.batch_df['success_rate'].mean()
        total_retries = self.batch_df['total_retries'].sum()
        
        # Performance trends
        throughput_trend = 'increasing' if self.batch_df['throughput'].iloc[-1] > self.batch_df['throughput'].iloc[0] else 'decreasing'
        
        report_content = f"""
# Progressive Test Analysis Report

## Test Overview
- **Test Name**: {self.data['test_name']}
- **Test Duration**: {self.data.get('test_duration', 'N/A')} seconds
- **Total Workflows**: {self.data.get('total_workflows', 0)}
- **Overall Success Rate**: {self.data.get('overall_success_rate', 0):.2f}%

## Performance Summary
- **Maximum Throughput**: {max_throughput:.2f} workflows/s
- **Optimal Batch Size**: {optimal_batch_size}
- **Average Success Rate**: {avg_success_rate:.2f}%
- **Total Retries**: {total_retries}
- **Throughput Trend**: {throughput_trend}

## Scalability Analysis
- **Linear Scaling Range**: Batch sizes 1-{optimal_batch_size}
- **Performance Plateau**: {optimal_batch_size}+ batch sizes
- **Efficiency Score**: {(max_throughput / optimal_batch_size):.3f}

## Anomaly Detection Results
- **Total Anomalies Detected**: {anomalies['summary']['total_anomalies']}
- **Throughput Anomalies**: {anomalies['summary']['throughput_anomaly_count']}
- **Execution Time Anomalies**: {anomalies['summary']['execution_time_anomaly_count']}
- **Success Rate Anomalies**: {anomalies['summary']['success_rate_anomaly_count']}

### Detailed Anomalies
"""
        
        # Add detailed anomaly information
        if anomalies['throughput_anomalies']:
            report_content += "\n#### Throughput Anomalies\n"
            for anomaly in anomalies['throughput_anomalies']:
                report_content += f"- Batch size {anomaly['batch_size']}: {anomaly['value']:.2f} workflows/s (z-score: {anomaly['z_score']:.2f})\n"
        
        if anomalies['execution_time_anomalies']:
            report_content += "\n#### Execution Time Anomalies\n"
            for anomaly in anomalies['execution_time_anomalies']:
                report_content += f"- Batch size {anomaly['batch_size']}: {anomaly['value']:.3f}s (z-score: {anomaly['z_score']:.2f})\n"
        
        if anomalies['success_rate_anomalies']:
            report_content += "\n#### Success Rate Anomalies\n"
            for anomaly in anomalies['success_rate_anomalies']:
                report_content += f"- Batch size {anomaly['batch_size']}: {anomaly['value']:.1f}% success rate\n"
        
        # Recommendations
        report_content += f"""

## Recommendations

### Performance Optimization
- **Recommended Batch Size**: {optimal_batch_size} (achieves maximum throughput)
- **Scaling Strategy**: {'Linear scaling observed up to batch size ' + str(optimal_batch_size) if optimal_batch_size > 1 else 'Consider investigating bottlenecks'}

### Reliability Improvements
"""
        
        if total_retries > 0:
            report_content += f"- **Retry Optimization**: {total_retries} total retries detected. Consider investigating failure patterns.\n"
        
        if avg_success_rate < 99.0:
            report_content += f"- **Success Rate**: Average success rate is {avg_success_rate:.1f}%. Investigate failure causes.\n"
        
        report_content += """

### Monitoring Recommendations
- Monitor throughput degradation beyond optimal batch size
- Set up alerts for success rates below 95%
- Track execution time variance as an early indicator of performance issues

---
*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Save report
        report_file = output_path / f"{self.data['test_name']}_analysis_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return str(report_file)

class TestComparator:
    """Compare multiple test runs for regression analysis."""
    
    def __init__(self, report_paths: List[str]):
        """Initialize comparator with multiple test report paths."""
        self.analyzers = [TestResultAnalyzer(path) for path in report_paths]
        self.test_names = [analyzer.data['test_name'] for analyzer in self.analyzers]
    
    def compare_performance(self, output_dir: str = "visualizations") -> str:
        """Generate comparison visualizations between test runs."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        colors = plt.cm.Set1(np.linspace(0, 1, len(self.analyzers)))
        
        # 1. Throughput Comparison
        for i, analyzer in enumerate(self.analyzers):
            ax1.plot(analyzer.batch_df['batch_size'], analyzer.batch_df['throughput'], 
                    'o-', label=self.test_names[i], color=colors[i], linewidth=2, markersize=6)
        ax1.set_xlabel('Batch Size')
        ax1.set_ylabel('Throughput (workflows/s)')
        ax1.set_title('Throughput Comparison')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Execution Time Comparison
        for i, analyzer in enumerate(self.analyzers):
            ax2.plot(analyzer.batch_df['batch_size'], analyzer.batch_df['avg_execution_time'], 
                    'o-', label=self.test_names[i], color=colors[i], linewidth=2, markersize=6)
        ax2.set_xlabel('Batch Size')
        ax2.set_ylabel('Average Execution Time (s)')
        ax2.set_title('Execution Time Comparison')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. Success Rate Comparison
        for i, analyzer in enumerate(self.analyzers):
            ax3.plot(analyzer.batch_df['batch_size'], analyzer.batch_df['success_rate'], 
                    'o-', label=self.test_names[i], color=colors[i], linewidth=2, markersize=6)
        ax3.set_xlabel('Batch Size')
        ax3.set_ylabel('Success Rate (%)')
        ax3.set_title('Success Rate Comparison')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. Performance Regression Detection
        if len(self.analyzers) >= 2:
            baseline = self.analyzers[0]
            current = self.analyzers[-1]
            
            # Calculate performance regression
            regression_data = []
            for batch_size in baseline.batch_df['batch_size']:
                baseline_throughput = baseline.batch_df[baseline.batch_df['batch_size'] == batch_size]['throughput'].iloc[0]
                current_throughput = current.batch_df[current.batch_df['batch_size'] == batch_size]['throughput'].iloc[0]
                regression_pct = ((current_throughput - baseline_throughput) / baseline_throughput) * 100
                regression_data.append(regression_pct)
            
            ax4.bar(baseline.batch_df['batch_size'], regression_data, 
                   color=['green' if x >= 0 else 'red' for x in regression_data], alpha=0.7)
            ax4.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            ax4.set_xlabel('Batch Size')
            ax4.set_ylabel('Performance Change (%)')
            ax4.set_title(f'Performance Regression: {self.test_names[-1]} vs {self.test_names[0]}')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        comparison_file = output_path / "test_comparison.png"
        plt.savefig(comparison_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(comparison_file)

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Visualization and Analysis Tool for Progressive Testing Framework"
    )
    
    parser.add_argument(
        'report_files',
        nargs='+',
        help='JSON report file(s) to analyze'
    )
    
    parser.add_argument(
        '--output-dir',
        default='visualizations',
        help='Output directory for visualizations (default: visualizations)'
    )
    
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare multiple test runs (requires multiple report files)'
    )
    
    parser.add_argument(
        '--analysis-only',
        action='store_true',
        help='Generate analysis report only (no visualizations)'
    )
    
    return parser.parse_args()

def main():
    """Main function for visualization and analysis."""
    args = parse_arguments()
    
    try:
        # Validate input files
        for report_file in args.report_files:
            if not Path(report_file).exists():
                print(f"❌ Error: Report file not found: {report_file}")
                return 1
        
        print(f"📊 Starting analysis of {len(args.report_files)} report(s)...")
        
        if args.compare and len(args.report_files) > 1:
            # Comparison mode
            print("🔍 Running comparison analysis...")
            comparator = TestComparator(args.report_files)
            comparison_file = comparator.compare_performance(args.output_dir)
            print(f"   ✅ Comparison visualization saved: {comparison_file}")
        
        # Individual analysis for each report
        for report_file in args.report_files:
            print(f"\n📈 Analyzing: {Path(report_file).name}")
            analyzer = TestResultAnalyzer(report_file)
            
            if not args.analysis_only:
                # Generate visualizations
                performance_files = analyzer.plot_performance_metrics(args.output_dir)
                scalability_files = analyzer.plot_scalability_analysis(args.output_dir)
                
                print(f"   ✅ Performance metrics: {', '.join([Path(f).name for f in performance_files])}")
                print(f"   ✅ Scalability analysis: {', '.join([Path(f).name for f in scalability_files])}")
            
            # Generate analysis report
            report_file_path = analyzer.generate_analysis_report(args.output_dir)
            print(f"   ✅ Analysis report: {Path(report_file_path).name}")
            
            # Print anomaly summary
            anomalies = analyzer.detect_anomalies()
            if anomalies['summary']['total_anomalies'] > 0:
                print(f"   ⚠️  {anomalies['summary']['total_anomalies']} anomalies detected")
            else:
                print(f"   ✅ No anomalies detected")
        
        print(f"\n🎉 Analysis completed! Results saved to: {args.output_dir}")
        return 0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())