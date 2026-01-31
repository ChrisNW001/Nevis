#!/usr/bin/env python3
"""Simple web viewer for Customer Segmentation Analysis results.

This is a focused viewer that ONLY displays the segmentation analysis -
no other features.

Usage:
    python scripts/run_analysis_viewer.py
    python scripts/run_analysis_viewer.py --port 8080
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flask import Flask, render_template_string

app = Flask(__name__)

# Load analysis data
ANALYSIS_DATA = None


def load_analysis():
    """Load the analysis results."""
    global ANALYSIS_DATA

    analysis_path = Path.home() / ".nevis" / "analysis_results.json"

    if analysis_path.exists():
        with open(analysis_path, 'r', encoding='utf-8') as f:
            ANALYSIS_DATA = json.load(f)
    else:
        ANALYSIS_DATA = None


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kundensegmentierung - Analyse</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --success: #16a34a;
            --warning: #d97706;
            --danger: #dc2626;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --muted: #64748b;
            --border: #e2e8f0;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }

        .header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }

        .header h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .header .subtitle { opacity: 0.9; }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .nav-tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }

        .nav-tab {
            padding: 0.75rem 1.5rem;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }

        .nav-tab:hover { border-color: var(--primary); color: var(--primary); }
        .nav-tab.active { background: var(--primary); color: white; border-color: var(--primary); }

        .section { display: none; }
        .section.active { display: block; }

        .card {
            background: var(--card);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .card h2 {
            font-size: 1.25rem;
            margin-bottom: 1rem;
            color: var(--primary);
        }

        .card h3 {
            font-size: 1rem;
            margin: 1rem 0 0.5rem;
            color: var(--text);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--card);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .stat-number { font-size: 2rem; font-weight: 700; color: var(--primary); }
        .stat-label { color: var(--muted); font-size: 0.875rem; }

        .segment-card {
            border-left: 4px solid var(--primary);
            margin-bottom: 2rem;
        }

        .segment-card.priority-a { border-color: var(--success); }
        .segment-card.priority-b { border-color: var(--warning); }
        .segment-card.priority-c { border-color: var(--muted); }

        .segment-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .segment-name { font-size: 1.5rem; font-weight: 700; }

        .priority-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
        }

        .priority-a { background: #dcfce7; color: #166534; }
        .priority-b { background: #fef3c7; color: #92400e; }
        .priority-c { background: #f1f5f9; color: #475569; }

        .grid-2 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
        }

        .tag-list { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0; }

        .tag {
            background: var(--bg);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
        }

        .quote {
            background: var(--bg);
            padding: 1rem;
            border-left: 3px solid var(--primary);
            border-radius: 0 8px 8px 0;
            margin: 0.5rem 0;
            font-style: italic;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }

        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        th {
            font-weight: 600;
            color: var(--muted);
            font-size: 0.75rem;
            text-transform: uppercase;
        }

        .score-bar {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .score-fill {
            height: 8px;
            background: var(--primary);
            border-radius: 4px;
        }

        .disc-badge {
            display: inline-block;
            width: 32px;
            height: 32px;
            line-height: 32px;
            text-align: center;
            border-radius: 50%;
            font-weight: 700;
            color: white;
        }

        .disc-d { background: #dc2626; }
        .disc-i { background: #f59e0b; }
        .disc-s { background: #10b981; }
        .disc-c { background: #3b82f6; }

        .forces-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
            margin: 1rem 0;
        }

        .force-box {
            padding: 1rem;
            border-radius: 8px;
        }

        .force-push { background: #fee2e2; border: 1px solid #fecaca; }
        .force-pull { background: #dcfce7; border: 1px solid #bbf7d0; }
        .force-anxiety { background: #fef3c7; border: 1px solid #fde68a; }
        .force-habit { background: #e0e7ff; border: 1px solid #c7d2fe; }

        .force-title { font-weight: 600; margin-bottom: 0.5rem; }

        ul { padding-left: 1.5rem; }
        li { margin: 0.25rem 0; }

        .messaging-box {
            background: var(--bg);
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
        }

        .value-prop {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--primary);
            padding: 1rem;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-radius: 8px;
            margin: 1rem 0;
        }

        .objection-item {
            background: var(--bg);
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
        }

        .objection-q { font-weight: 600; color: var(--danger); }
        .objection-a { color: var(--success); margin-top: 0.5rem; }

        .empty-state {
            text-align: center;
            padding: 4rem;
            color: var(--muted);
        }

        .clv-highlight {
            font-size: 2rem;
            font-weight: 700;
            color: var(--success);
        }

        @media (max-width: 768px) {
            .grid-2 { grid-template-columns: 1fr; }
            .forces-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Kundensegmentierung</h1>
        <div class="subtitle">Analyse nach Vorgehensmodell</div>
    </div>

    <div class="container">
        {% if analysis %}

        <!-- Navigation -->
        <div class="nav-tabs">
            <div class="nav-tab active" onclick="showSection('overview')">Ueberblick</div>
            <div class="nav-tab" onclick="showSection('themes')">Themen & Codes</div>
            <div class="nav-tab" onclick="showSection('psycho')">Psychografie</div>
            <div class="nav-tab" onclick="showSection('segments')">Segmente</div>
            <div class="nav-tab" onclick="showSection('strategy')">Strategie</div>
        </div>

        <!-- Overview Section -->
        <div id="overview" class="section active">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{{ metadata.meetings_count }}</div>
                    <div class="stat-label">Analysierte Meetings</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ (analysis.analysis_metadata.avg_duration_minutes|default(0))|round(0)|int if analysis.analysis_metadata else 'N/A' }}</div>
                    <div class="stat-label">Durchschn. Dauer (Min)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ segments|length if segments else 0 }}</div>
                    <div class="stat-label">Identifizierte Segmente</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ focus_segments|length if focus_segments else 0 }}</div>
                    <div class="stat-label">Fokus-Segmente</div>
                </div>
            </div>

            <div class="card">
                <h2>Analysierte Meetings</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Datum</th>
                            <th>Titel</th>
                            <th>Dauer</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for m in metadata.meetings %}
                        <tr>
                            <td>{{ m.date[:10] if m.date else 'N/A' }}</td>
                            <td>{{ m.title }}</td>
                            <td>{{ (m.duration_minutes|default(0))|round(0)|int }} min</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            {% if focus_segments %}
            <div class="card">
                <h2>Fokus-Segmente (Empfehlung)</h2>
                <div class="tag-list">
                    {% for seg in focus_segments %}
                    <span class="tag" style="background: #dcfce7; color: #166534;">{{ seg }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>

        <!-- Themes Section -->
        <div id="themes" class="section">
            {% if themes %}
            <div class="card">
                <h2>Identifizierte Themen</h2>
                {% for theme in themes %}
                <div style="margin-bottom: 1.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--border);">
                    <h3>{{ theme.name }} ({{ theme.frequency_percent }}%)</h3>
                    <p>{{ theme.description }}</p>
                    <div class="tag-list">
                        {% for code in theme.codes %}
                        <span class="tag">{{ code }}</span>
                        {% endfor %}
                    </div>
                    {% for quote in theme.typical_quotes %}
                    <div class="quote">"{{ quote }}"</div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% if code_frequency %}
            <div class="card">
                <h2>Code-Haeufigkeit</h2>
                <table>
                    <thead>
                        <tr><th>Code</th><th>Anzahl</th><th>Verteilung</th></tr>
                    </thead>
                    <tbody>
                        {% for code, count in code_frequency.items() %}
                        <tr>
                            <td>{{ code }}</td>
                            <td>{{ count }}</td>
                            <td>
                                <div class="score-bar">
                                    <div class="score-fill" style="width: {{ ((count|default(0)) / (max_code_count|default(1)) * 100)|round(0) }}px;"></div>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
        </div>

        <!-- Psychographic Section -->
        <div id="psycho" class="section">
            {% if disc_profiles %}
            <div class="card">
                <h2>DISC-Profile</h2>
                <div class="grid-2">
                    {% for profile in disc_profiles %}
                    <div style="background: var(--bg); padding: 1rem; border-radius: 8px;">
                        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                            <span class="disc-badge disc-{{ profile.primary_type|lower }}">{{ profile.primary_type }}</span>
                            <div>
                                <strong>{{ profile.name }}</strong>
                                <div style="font-size: 0.875rem; color: var(--muted);">{{ profile.role }}</div>
                            </div>
                        </div>
                        <p style="font-size: 0.875rem;">{{ profile.communication_recommendation }}</p>
                        <div style="margin-top: 0.5rem;">
                            {% for ev in profile.evidence[:2] %}
                            <div class="quote" style="font-size: 0.875rem;">"{{ ev }}"</div>
                            {% endfor %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            {% if forces %}
            <div class="card">
                <h2>Forces of Progress</h2>
                <div class="forces-grid">
                    <div class="force-box force-push">
                        <div class="force-title">PUSH (Weg vom Status Quo)</div>
                        <ul>
                            {% for item in forces.push %}
                            <li>{{ item }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    <div class="force-box force-pull">
                        <div class="force-title">PULL (Hin zur Loesung)</div>
                        <ul>
                            {% for item in forces.pull %}
                            <li>{{ item }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    <div class="force-box force-anxiety">
                        <div class="force-title">ANXIETY (Bedenken)</div>
                        <ul>
                            {% for item in forces.anxiety %}
                            <li>{{ item }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    <div class="force-box force-habit">
                        <div class="force-title">HABIT (Gewohnheit)</div>
                        <ul>
                            {% for item in forces.habit %}
                            <li>{{ item }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                </div>
            </div>
            {% endif %}

            {% if jobs %}
            <div class="card">
                <h2>Jobs-to-be-Done</h2>
                {% for job in jobs %}
                <div class="messaging-box">
                    <strong>{{ job.job_statement }}</strong>
                    <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                        <span class="tag">Funktional: {{ job.functional_job }}</span>
                        <span class="tag">Emotional: {{ job.emotional_job }}</span>
                        <span class="tag">Sozial: {{ job.social_job }}</span>
                    </div>
                    {% if job.original_quote %}
                    <div class="quote" style="margin-top: 0.5rem;">"{{ job.original_quote }}"</div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% if needs %}
            <div class="card">
                <h2>Beduerfnisse (Kano-Klassifikation)</h2>
                <table>
                    <thead>
                        <tr><th>ID</th><th>Beduerfnis</th><th>Kano-Typ</th><th>Haeufigkeit</th><th>Prioritaet</th></tr>
                    </thead>
                    <tbody>
                        {% for need in needs %}
                        <tr>
                            <td>{{ need.id }}</td>
                            <td>{{ need.description }}</td>
                            <td><span class="tag">{{ need.kano_type }}</span></td>
                            <td>{{ need.frequency_percent }}%</td>
                            <td>{{ need.priority }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
        </div>

        <!-- Segments Section -->
        <div id="segments" class="section">
            {% if segments %}
            {% for seg in segments %}
            <div class="card segment-card priority-{{ seg.priority|lower }}">
                <div class="segment-header">
                    <div class="segment-name">{{ seg.name }}</div>
                    <span class="priority-badge priority-{{ seg.priority|lower }}">Prioritaet {{ seg.priority }}</span>
                </div>
                <p style="margin-bottom: 1.5rem;">{{ seg.description }}</p>

                <div class="grid-2">
                    <div>
                        <h3>Firmographics</h3>
                        <table>
                            <tr><td><strong>Branchen</strong></td><td>{{ seg.firmographics.industries|join(', ') }}</td></tr>
                            <tr><td><strong>Unternehmensgroesse</strong></td><td>{{ seg.firmographics.company_sizes|join(', ') }}</td></tr>
                            <tr><td><strong>Umsatz</strong></td><td>{{ seg.firmographics.revenue_range }}</td></tr>
                            <tr><td><strong>Tech-Maturity</strong></td><td>{{ seg.firmographics.tech_maturity }}</td></tr>
                        </table>
                    </div>
                    <div>
                        <h3>Psychographics</h3>
                        <table>
                            <tr>
                                <td><strong>DISC-Typ</strong></td>
                                <td><span class="disc-badge disc-{{ seg.psychographics.primary_disc|lower }}">{{ seg.psychographics.primary_disc }}</span></td>
                            </tr>
                            <tr><td><strong>Entscheidungsstil</strong></td><td>{{ seg.psychographics.decision_style }}</td></tr>
                            <tr><td><strong>Risikobereitschaft</strong></td><td>{{ seg.psychographics.risk_tolerance }}</td></tr>
                            <tr><td><strong>Innovationsaffinitaet</strong></td><td>{{ seg.psychographics.innovation_affinity }}</td></tr>
                        </table>
                    </div>
                </div>

                <div class="grid-2" style="margin-top: 1rem;">
                    <div>
                        <h3>Top Pain Points</h3>
                        <ul>
                            {% for pp in seg.pain_points %}
                            <li>{{ pp }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    <div>
                        <h3>Jobs-to-be-Done</h3>
                        <ul>
                            {% for job in seg.jobs_to_be_done %}
                            <li>{{ job }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                </div>

                <div class="grid-2" style="margin-top: 1rem;">
                    <div>
                        <h3>Typische Einwaende</h3>
                        <div class="tag-list">
                            {% for obj in seg.objections %}
                            <span class="tag" style="background: #fee2e2;">{{ obj }}</span>
                            {% endfor %}
                        </div>
                    </div>
                    <div>
                        <h3>Kaufsignale</h3>
                        <div class="tag-list">
                            {% for sig in seg.buying_signals %}
                            <span class="tag" style="background: #dcfce7;">{{ sig }}</span>
                            {% endfor %}
                        </div>
                    </div>
                </div>

                {% if seg.typical_quotes %}
                <h3 style="margin-top: 1rem;">Typische Zitate</h3>
                {% for quote in seg.typical_quotes %}
                <div class="quote">"{{ quote }}"</div>
                {% endfor %}
                {% endif %}

                <div class="grid-2" style="margin-top: 1.5rem;">
                    <div>
                        {% if seg.scoring %}
                        <h3>Scoring</h3>
                        <table>
                            <tr>
                                <td>Fit-Score</td>
                                <td>
                                    <div class="score-bar">
                                        <div class="score-fill" style="width: {{ seg.scoring.fit_score|default(0) }}px;"></div>
                                        <span>{{ seg.scoring.fit_score|default(0) }}</span>
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td>Value-Score</td>
                                <td>
                                    <div class="score-bar">
                                        <div class="score-fill" style="width: {{ seg.scoring.value_score|default(0) }}px;"></div>
                                        <span>{{ seg.scoring.value_score|default(0) }}</span>
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td>Engagement-Score</td>
                                <td>
                                    <div class="score-bar">
                                        <div class="score-fill" style="width: {{ seg.scoring.engagement_score|default(0) }}px;"></div>
                                        <span>{{ seg.scoring.engagement_score|default(0) }}</span>
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td><strong>Gesamt-Score</strong></td>
                                <td><strong>{{ seg.scoring.total_score|default(0) }}</strong></td>
                            </tr>
                        </table>
                        {% endif %}
                    </div>
                    <div>
                        {% if seg.clv %}
                        <h3>Customer Lifetime Value</h3>
                        <div class="clv-highlight">{{ "{:,.0f}".format(seg.clv.total_clv|default(0)) }} EUR</div>
                        <table style="margin-top: 0.5rem;">
                            <tr><td>Erstauftrag</td><td>{{ "{:,.0f}".format(seg.clv.first_order|default(0)) }} EUR</td></tr>
                            <tr><td>Jaehrl. Recurring</td><td>{{ "{:,.0f}".format(seg.clv.recurring|default(0)) }} EUR</td></tr>
                            <tr><td>Lebensdauer</td><td>{{ seg.clv.lifetime_years|default('N/A') }} Jahre</td></tr>
                            <tr><td>Win-Rate</td><td>{{ seg.clv.win_rate_percent|default(0) }}%</td></tr>
                            <tr><td>Aufwand</td><td>{{ seg.clv.effort|default('N/A') }}</td></tr>
                        </table>
                        {% endif %}
                    </div>
                </div>

                {% if seg.sales_cycle %}
                <h3 style="margin-top: 1rem;">Sales Cycle</h3>
                <p><strong>Durchschnittliche Laenge:</strong> {{ seg.sales_cycle.avg_length }}</p>
                <div class="tag-list">
                    {% for phase in seg.sales_cycle.phases %}
                    <span class="tag">{{ phase }}</span>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
            {% else %}
            <div class="empty-state">
                <p>Keine Segmente gefunden.</p>
            </div>
            {% endif %}
        </div>

        <!-- Strategy Section -->
        <div id="strategy" class="section">
            {% if focus_segments %}
            <div class="card">
                <h2>Fokus-Segmente</h2>
                <div class="tag-list">
                    {% for seg in focus_segments %}
                    <span class="tag" style="background: #dcfce7; color: #166534; font-size: 1rem; padding: 0.5rem 1rem;">{{ seg }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            {% if messaging %}
            {% for seg_name, msg in messaging.items() %}
            <div class="card">
                <h2>Messaging: {{ seg_name }}</h2>

                {% if msg.value_proposition %}
                <div class="value-prop">{{ msg.value_proposition }}</div>
                {% endif %}

                {% if msg.pillars %}
                <h3>Messaging Pillars</h3>
                <ul>
                    {% for pillar in msg.pillars %}
                    <li>{{ pillar }}</li>
                    {% endfor %}
                </ul>
                {% endif %}

                {% if msg.proof_points %}
                <h3>Proof Points</h3>
                <ul>
                    {% for pp in msg.proof_points %}
                    <li>{{ pp }}</li>
                    {% endfor %}
                </ul>
                {% endif %}

                {% if msg.objection_handling %}
                <h3>Einwand-Handling</h3>
                {% for obj, response in msg.objection_handling.items() %}
                <div class="objection-item">
                    <div class="objection-q">Einwand: "{{ obj }}"</div>
                    <div class="objection-a">Antwort: {{ response }}</div>
                </div>
                {% endfor %}
                {% endif %}

                {% if msg.disc_adaptation %}
                <h3>DISC-Anpassung</h3>
                <div class="grid-2">
                    <div class="messaging-box">
                        <span class="disc-badge disc-d">D</span>
                        <p style="margin-top: 0.5rem;">{{ msg.disc_adaptation.D }}</p>
                    </div>
                    <div class="messaging-box">
                        <span class="disc-badge disc-i">I</span>
                        <p style="margin-top: 0.5rem;">{{ msg.disc_adaptation.I }}</p>
                    </div>
                    <div class="messaging-box">
                        <span class="disc-badge disc-s">S</span>
                        <p style="margin-top: 0.5rem;">{{ msg.disc_adaptation.S }}</p>
                    </div>
                    <div class="messaging-box">
                        <span class="disc-badge disc-c">C</span>
                        <p style="margin-top: 0.5rem;">{{ msg.disc_adaptation.C }}</p>
                    </div>
                </div>
                {% endif %}
            </div>
            {% endfor %}
            {% endif %}

            {% if recommendations %}
            <div class="card">
                <h2>Strategische Empfehlungen</h2>
                <ul>
                    {% for rec in recommendations %}
                    <li style="margin: 0.5rem 0;">{{ rec }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>

        {% else %}
        <div class="empty-state">
            <h2>Keine Analyse vorhanden</h2>
            <p style="margin: 1rem 0;">Fuehren Sie zuerst die Analyse aus:</p>
            <code style="background: #1e293b; color: #10b981; padding: 1rem; border-radius: 8px; display: block;">
                python scripts/run_segmentation_analysis.py --participant "Felix Wietschke"
            </code>
        </div>
        {% endif %}
    </div>

    <script>
        function showSection(sectionId) {
            // Hide all sections
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));

            // Show selected section
            document.getElementById(sectionId).classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Render the analysis viewer."""
    load_analysis()

    if not ANALYSIS_DATA:
        return render_template_string(HTML_TEMPLATE, analysis=None)

    # Extract data for template
    metadata = ANALYSIS_DATA.get('_metadata', {})
    analysis = ANALYSIS_DATA

    # Phase 2
    phase2 = analysis.get('phase2_thematic_analysis', {})
    themes = phase2.get('themes', [])
    code_frequency = phase2.get('code_frequency', {})
    max_code_count = max(code_frequency.values()) if code_frequency else 1

    # Phase 3
    phase3 = analysis.get('phase3_psychographic', {})
    disc_profiles = phase3.get('disc_profiles', [])
    jobs = phase3.get('jobs_to_be_done', [])
    forces = phase3.get('forces_of_progress', {})
    needs = phase3.get('needs', [])

    # Phase 4
    segments = analysis.get('phase4_segments', [])

    # Phase 5
    phase5 = analysis.get('phase5_strategy', {})
    focus_segments = phase5.get('focus_segments', [])
    messaging = phase5.get('messaging', {})
    recommendations = phase5.get('recommendations', [])

    return render_template_string(
        HTML_TEMPLATE,
        analysis=analysis,
        metadata=metadata,
        themes=themes,
        code_frequency=code_frequency,
        max_code_count=max_code_count,
        disc_profiles=disc_profiles,
        jobs=jobs,
        forces=forces,
        needs=needs,
        segments=segments,
        focus_segments=focus_segments,
        messaging=messaging,
        recommendations=recommendations,
    )


def main():
    parser = argparse.ArgumentParser(description="View Customer Segmentation Analysis")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind to")

    args = parser.parse_args()

    print(f"""
    ================================================
    Kundensegmentierung - Analyse Viewer
    ================================================

    Oeffnen Sie Ihren Browser: http://{args.host}:{args.port}

    Druecken Sie Strg+C zum Beenden.
    ================================================
    """)

    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
