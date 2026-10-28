"""
prepare_data.py - SkillsGap (Team ArgonUT, HackSpire Lumina, UNITEN)

Rebuilds these files from the raw Kaggle dataset
"LinkedIn Job Postings (2023 - 2024)" (https://www.kaggle.com/datasets/arshkon/linkedin-job-postings, CC BY-SA 4.0):

    data/skills.csv
    data/role_skill_demand.csv
    data/data_source.json

The raw postings.csv is NOT part of the repo. Download it from Kaggle and pass its path.

Usage (Python 3.12 + pandas):
    python prepare_data.py --raw postings.csv                 # build all output files
    python prepare_data.py --raw postings.csv --counts-only   # only print postings per role
    python prepare_data.py --raw postings.csv --hand-check 20 # also print 20 random matches to check by hand
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import pandas as pd

OUT_DIR = Path("data")
LOW_SAMPLE_LIMIT = 30

# ---------------------------------------------------------------------------
# 1. Title -> role mapping
# A posting goes to the FIRST role (in this order) whose keyword phrase appears
# in the lower-cased title as a whole word/phrase. Each posting gets one role only.
# ---------------------------------------------------------------------------
ROLE_KEYWORDS: dict[str, list[str]] = {
    "Data Analyst": [
        "data analyst", "data analytics analyst", "analytics analyst",
        "business intelligence analyst", "bi analyst",
    ],
    "Cybersecurity Analyst": [
        "cybersecurity analyst", "cyber security analyst", "cyber-security analyst",
        "security analyst", "soc analyst", "security operations analyst",
        "cyber analyst", "cyber threat analyst", "threat intelligence analyst",
        "incident response analyst", "vulnerability analyst", "penetration tester",
        "cybersecurity engineer", "cyber security engineer", "security engineer",
        "cybersecurity specialist", "cyber security specialist", "information security specialist",
        "cybersecurity consultant", "cyber security consultant",
    ],
    "Software Engineer": [
        "software engineer", "software developer", "software development engineer",
        "software engineering",
        "full stack developer", "full stack engineer", "full-stack developer",
        "full-stack engineer", "fullstack developer", "fullstack engineer",
        "backend developer", "backend engineer", "back end developer", "back end engineer",
        "back-end developer", "back-end engineer",
        "frontend developer", "frontend engineer", "front end developer", "front end engineer",
        "front-end developer", "front-end engineer",
        "web developer", "application developer", "applications developer",
        "java developer", "python developer", ".net developer", "dotnet developer",
        "c# developer", "ios developer", "android developer", "mobile developer",
        "react developer", "javascript developer",
    ],
    "Data Scientist": [
        "data scientist", "data science", "machine learning engineer",
        "machine learning scientist", "ml engineer", "applied scientist",
    ],
    "Network Engineer": [
        "network engineer", "network engineering", "network administrator", "network architect",
    ],
    "Cloud Engineer": [
        "cloud engineer", "cloud architect", "cloud solutions architect",
        "cloud infrastructure engineer", "cloud platform engineer", "cloud operations engineer",
        "cloud developer", "cloud administrator", "cloud consultant",
        "devops engineer", "devops architect",
        "aws engineer", "aws architect", "azure engineer", "azure architect", "gcp engineer",
    ],
    "Electrical Engineer": [
        "electrical engineer", "electrical engineering", "electrical design engineer",
        "electrical designer", "electrical controls engineer", "electrical project engineer",
        "power systems engineer",
    ],
    "Mechanical Engineer": [
        "mechanical engineer", "mechanical engineering", "mechanical design engineer",
        "mechanical designer", "mechanical project engineer",
    ],
    "Civil Engineer": [
        "civil engineer", "civil engineering", "structural engineer", "geotechnical engineer",
        "transportation engineer", "traffic engineer", "water resources engineer",
    ],
    "UI/UX Designer": [
        "ui/ux designer", "ux/ui designer", "ui/ux", "ux/ui", "ux designer", "ui designer",
        "ux researcher", "ux research", "ux lead", "ux architect",
        "user experience designer", "user experience researcher", "user experience specialist",
        "user experience lead", "user interface designer", "product designer", "interaction designer",
    ],
    "Business Analyst": [
        "business analyst", "business systems analyst", "business analysis",
    ],
    "Project Manager": [
        "project manager",
    ],
}

# Titles containing any of these are skipped for every role (not the actual job).
TITLE_EXCLUDE = [
    "recruiter", "recruiting", "recruitment", "sales", "business development",
    "technician", "instructor", "professor", "teacher", "lecturer", "faculty",
]

# ---------------------------------------------------------------------------
# 2. Skill dictionary: skill -> (category, synonyms)
# Synonyms must not contain commas or semicolons.
# ---------------------------------------------------------------------------
SKILLS: dict[str, tuple[str, list[str]]] = {
    # Programming
    "Python": ("Programming", ["python3", "python 3"]),
    "R": ("Programming", ["R programming", "R language", "RStudio", "R Shiny"]),
    "SQL": ("Programming", ["structured query language", "t-sql", "tsql", "pl/sql"]),
    "Java": ("Programming", ["java ee", "j2ee"]),
    "JavaScript": ("Programming", ["js", "ecmascript", "es6"]),
    "TypeScript": ("Programming", []),
    "C++": ("Programming", ["cpp"]),
    "C#": ("Programming", ["c-sharp", "csharp"]),
    "C": ("Programming", ["C language", "C programming", "ANSI C", "embedded C"]),
    "Go": ("Programming", ["golang", "Go language", "Go programming"]),
    ".NET": ("Programming", ["dotnet", "asp.net", ".net core"]),
    "HTML": ("Programming", ["html5"]),
    "CSS": ("Programming", ["css3", "sass", "scss"]),
    "React": ("Programming", ["react.js", "reactjs"]),
    "Node.js": ("Programming", ["nodejs", "node js"]),
    "Bash": ("Programming", ["shell scripting", "bash scripting", "shell script", "unix shell"]),
    "PowerShell": ("Programming", []),
    # Software Engineering
    "REST APIs": ("Software Engineering", ["rest api", "restful", "restful api", "restful apis",
                                          "restful services", "rest services"]),
    "Microservices": ("Software Engineering", ["microservice", "micro-services"]),
    "Unit Testing": ("Software Engineering", ["unit tests", "unit test", "test-driven development",
                                             "tdd", "junit", "pytest"]),
    "Object-Oriented Programming": ("Software Engineering", ["oop", "object oriented programming",
                                                            "object-oriented design", "object oriented design"]),
    "Data Structures & Algorithms": ("Software Engineering", ["data structures", "algorithms"]),
    "System Design": ("Software Engineering", ["software architecture", "distributed systems"]),
    "Git": ("Software Engineering", ["github", "gitlab", "bitbucket", "version control"]),
    # Data Tools
    "Excel": ("Data Tools", ["microsoft excel", "ms excel"]),
    "Pandas": ("Data Tools", []),
    "NumPy": ("Data Tools", []),
    "Scikit-learn": ("Data Tools", ["sklearn", "scikit learn"]),
    "TensorFlow": ("Data Tools", ["keras"]),
    "PyTorch": ("Data Tools", []),
    "Apache Spark": ("Data Tools", ["Spark", "pyspark", "spark sql"]),
    "Databricks": ("Data Tools", []),
    "Jupyter": ("Data Tools", ["jupyter notebook", "jupyter notebooks", "jupyterlab"]),
    "ETL": ("Data Tools", ["extract transform load", "data pipeline", "data pipelines", "elt"]),
    "Data Warehousing": ("Data Tools", ["data warehouse", "data warehouses"]),
    "Snowflake": ("Data Tools", []),
    "SAS": ("Data Tools", []),
    "SPSS": ("Data Tools", ["ibm spss"]),
    "Google Analytics": ("Data Tools", ["ga4"]),
    "Data Cleaning": ("Data Tools", ["data cleansing", "data wrangling", "data preparation"]),
    "Data Modeling": ("Data Tools", ["data modelling"]),
    # Databases
    "NoSQL": ("Databases", ["mongodb", "cassandra", "dynamodb", "couchbase"]),
    # Statistics & ML
    "Statistics": ("Statistics & ML", ["statistical analysis", "statistical modeling",
                                       "statistical modelling", "statistical methods"]),
    "Machine Learning": ("Statistics & ML", ["ML"]),
    "Deep Learning": ("Statistics & ML", ["neural network", "neural networks"]),
    "NLP": ("Statistics & ML", ["natural language processing"]),
    "Computer Vision": ("Statistics & ML", []),
    "Generative AI": ("Statistics & ML", ["genai", "gen ai", "large language models",
                                          "large language model", "llm", "llms"]),
    "Regression Analysis": ("Statistics & ML", ["linear regression", "logistic regression",
                                                "regression models"]),
    "A/B Testing": ("Statistics & ML", ["a/b test", "a/b tests", "ab testing", "split testing"]),
    "Predictive Modeling": ("Statistics & ML", ["predictive modelling", "predictive models",
                                                "predictive analytics"]),
    "Time Series Analysis": ("Statistics & ML", ["time series", "time-series", "forecasting"]),
    # Visualisation
    "Tableau": ("Visualisation", []),
    "Power BI": ("Visualisation", ["powerbi", "power-bi"]),
    "Looker": ("Visualisation", ["looker studio"]),
    "Qlik": ("Visualisation", ["qlikview", "qlik sense"]),
    "Data Visualisation": ("Visualisation", ["data visualization", "dashboards", "dashboarding"]),
    # Cloud & DevOps
    "AWS": ("Cloud & DevOps", ["amazon web services", "ec2"]),
    "Azure": ("Cloud & DevOps", ["microsoft azure"]),
    "GCP": ("Cloud & DevOps", ["google cloud platform", "google cloud"]),
    "Docker": ("Cloud & DevOps", []),
    "Kubernetes": ("Cloud & DevOps", ["k8s", "eks", "aks", "gke", "openshift"]),
    "Terraform": ("Cloud & DevOps", []),
    "Ansible": ("Cloud & DevOps", []),
    "Jenkins": ("Cloud & DevOps", []),
    "CI/CD": ("Cloud & DevOps", ["continuous integration", "continuous delivery",
                                 "continuous deployment"]),
    "Infrastructure as Code": ("Cloud & DevOps", ["iac", "cloudformation", "bicep", "pulumi"]),
    "Serverless": ("Cloud & DevOps", ["aws lambda", "azure functions", "cloud functions"]),
    "Monitoring Tools": ("Cloud & DevOps", ["prometheus", "grafana", "datadog", "new relic",
                                           "cloudwatch", "nagios"]),
    "Linux": ("Cloud & DevOps", ["unix", "rhel", "red hat", "ubuntu"]),
    "Cloud Cost Optimization": ("Cloud & DevOps", ["cost optimization", "finops", "cloud cost"]),
    "MLOps": ("Cloud & DevOps", ["model deployment", "mlflow", "kubeflow", "sagemaker"]),
    # Security
    "SIEM": ("Security", ["security information and event management", "splunk", "qradar",
                          "microsoft sentinel", "arcsight"]),
    "Incident Response": ("Security", ["incident handling", "IR"]),
    "Vulnerability Management": ("Security", ["vulnerability assessment", "vulnerability assessments",
                                              "vulnerability scanning", "nessus", "qualys"]),
    "Penetration Testing": ("Security", ["pen testing", "pentesting", "pentest", "ethical hacking"]),
    "Firewalls": ("Security", ["firewall", "palo alto", "fortinet", "fortigate", "check point"]),
    "IDS/IPS": ("Security", ["intrusion detection", "intrusion prevention", "IDS", "IPS"]),
    "Threat Intelligence": ("Security", ["threat intel", "cyber threat intelligence", "osint"]),
    "Endpoint Security": ("Security", ["edr", "endpoint detection and response", "crowdstrike",
                                       "carbon black", "antivirus"]),
    "Identity and Access Management": ("Security", ["iam", "identity management", "access management",
                                                    "privileged access management"]),
    "Active Directory": ("Security", ["azure ad", "entra id"]),
    "Encryption": ("Security", ["cryptography", "pki", "tls", "ssl"]),
    "Network Security": ("Security", []),
    "Cloud Security": ("Security", []),
    "Digital Forensics": ("Security", ["computer forensics", "forensic analysis"]),
    "Malware Analysis": ("Security", ["malware"]),
    "NIST": ("Security", ["nist csf", "nist 800-53", "nist cybersecurity framework"]),
    "ISO 27001": ("Security", ["iso/iec 27001", "iso27001"]),
    "Security Compliance": ("Security", ["pci dss", "pci-dss", "hipaa", "sox compliance", "gdpr",
                                         "fedramp", "cmmc"]),
    # Networking
    "TCP/IP": ("Networking", ["tcp", "udp", "osi model"]),
    "Routing and Switching": ("Networking", ["routing", "switching", "routers", "switches",
                                             "routing protocols"]),
    "BGP": ("Networking", ["border gateway protocol"]),
    "OSPF": ("Networking", []),
    "Cisco": ("Networking", ["cisco ios", "cisco asa", "meraki"]),
    "Juniper": ("Networking", ["junos"]),
    "VLAN": ("Networking", ["vlans", "802.1q"]),
    "VPN": ("Networking", ["vpns", "ipsec", "ssl vpn"]),
    "DNS": ("Networking", []),
    "DHCP": ("Networking", []),
    "LAN/WAN": ("Networking", ["lan", "wan", "local area network", "wide area network"]),
    "SD-WAN": ("Networking", ["sdwan", "software-defined wan"]),
    "Load Balancing": ("Networking", ["load balancer", "load balancers", "f5"]),
    "Wireless Networking": ("Networking", ["wi-fi", "wifi", "wlan", "802.11", "wireless networks"]),
    "Network Monitoring": ("Networking", ["solarwinds", "prtg", "netflow", "snmp"]),
    "Wireshark": ("Networking", ["packet capture", "packet analysis", "tcpdump"]),
    "QoS": ("Networking", ["quality of service"]),
    "MPLS": ("Networking", []),
    "Network Automation": ("Networking", ["netmiko", "netconf"]),
    "Troubleshooting": ("Networking", ["troubleshoot", "troubleshooting skills"]),
    "Cloud Networking": ("Networking", ["vpc", "vnet", "virtual private cloud"]),
    # Engineering Tools
    "AutoCAD": ("Engineering Tools", ["autocad electrical", "autocad mechanical"]),
    "CAD": ("Engineering Tools", ["computer-aided design", "computer aided design"]),
    "SolidWorks": ("Engineering Tools", ["solid works"]),
    "CATIA": ("Engineering Tools", []),
    "Creo": ("Engineering Tools", ["ptc creo", "pro/engineer"]),
    "Siemens NX": ("Engineering Tools", ["unigraphics"]),
    "ANSYS": ("Engineering Tools", []),
    "FEA": ("Engineering Tools", ["finite element analysis", "finite element"]),
    "CFD": ("Engineering Tools", ["computational fluid dynamics"]),
    "MATLAB": ("Engineering Tools", []),
    "Simulink": ("Engineering Tools", []),
    "Revit": ("Engineering Tools", ["autodesk revit"]),
    "Civil 3D": ("Engineering Tools", ["autocad civil 3d", "civil3d"]),
    "MicroStation": ("Engineering Tools", ["bentley microstation"]),
    "BIM": ("Engineering Tools", ["building information modeling", "building information modelling"]),
    "GIS": ("Engineering Tools", ["arcgis", "qgis", "geographic information system",
                                  "geographic information systems"]),
    "Structural Analysis Software": ("Engineering Tools", ["staad", "staad.pro", "staad pro", "risa",
                                                          "risa-3d", "etabs", "sap2000"]),
    "Hydraulic Modeling": ("Engineering Tools", ["hec-ras", "hec-hms", "hydraulic modelling",
                                                 "stormcad", "swmm"]),
    "Bluebeam": ("Engineering Tools", ["bluebeam revu"]),
    "PCB Design": ("Engineering Tools", ["pcb layout", "printed circuit board", "altium", "orcad"]),
    "PLC": ("Engineering Tools", ["plcs", "programmable logic controller",
                                  "programmable logic controllers", "ladder logic"]),
    "SCADA": ("Engineering Tools", []),
    # Engineering Methods
    "Circuit Design": ("Engineering Methods", ["circuit analysis", "schematic capture", "analog circuits"]),
    "Power Systems Analysis": ("Engineering Methods", ["power system studies", "power systems studies",
                                                       "load flow", "short circuit", "arc flash", "etap",
                                                       "skm", "easypower"]),
    "Power Distribution": ("Engineering Methods", ["electrical distribution", "switchgear",
                                                   "switchboards", "transformers"]),
    "Substation Design": ("Engineering Methods", ["substation", "substations"]),
    "NEC": ("Engineering Methods", ["national electrical code", "nfpa 70"]),
    "Lighting Design": ("Engineering Methods", ["photometric", "lighting layouts"]),
    "Motor Controls": ("Engineering Methods", ["motor control", "vfd", "vfds",
                                               "variable frequency drive", "variable frequency drives"]),
    "Control Systems": ("Engineering Methods", ["controls engineering", "control theory"]),
    "Embedded Systems": ("Engineering Methods", ["firmware", "microcontroller", "microcontrollers"]),
    "Instrumentation": ("Engineering Methods", ["i&c", "instrumentation and controls"]),
    "Commissioning": ("Engineering Methods", []),
    "Engineering Drawings": ("Engineering Methods", ["technical drawings", "blueprints",
                                                     "engineering drawing"]),
    "MEP": ("Engineering Methods", ["mechanical electrical and plumbing"]),
    "GD&T": ("Engineering Methods", ["geometric dimensioning and tolerancing",
                                     "geometric dimensioning & tolerancing"]),
    "Tolerance Analysis": ("Engineering Methods", ["tolerance stack-up", "tolerance stackup",
                                                   "stack-up analysis"]),
    "DFM": ("Engineering Methods", ["design for manufacturing", "design for manufacturability",
                                    "dfma", "design for assembly"]),
    "FMEA": ("Engineering Methods", ["dfmea", "pfmea", "failure mode and effects analysis",
                                     "failure modes and effects analysis"]),
    "Thermal Analysis": ("Engineering Methods", ["heat transfer", "thermodynamics", "thermal management"]),
    "HVAC": ("Engineering Methods", ["heating ventilation and air conditioning"]),
    "Lean Six Sigma": ("Engineering Methods", ["six sigma", "lean manufacturing", "kaizen", "5s"]),
    "Root Cause Analysis": ("Engineering Methods", ["root-cause analysis", "rca", "8d", "5 whys"]),
    "Materials Selection": ("Engineering Methods", ["material selection", "materials science",
                                                    "materials engineering"]),
    "Manufacturing Processes": ("Engineering Methods", ["machining", "injection molding",
                                                        "injection moulding", "sheet metal", "cnc"]),
    "Structural Design": ("Engineering Methods", ["structural analysis", "structural calculations",
                                                  "steel design", "concrete design"]),
    "Geotechnical Engineering": ("Engineering Methods", ["geotechnical", "soil mechanics",
                                                         "foundation design"]),
    "Stormwater Management": ("Engineering Methods", ["stormwater", "storm water", "drainage design",
                                                      "drainage"]),
    "Site Design & Grading": ("Engineering Methods", ["site design", "site development", "grading plans",
                                                      "grading", "land development"]),
    "Transportation Engineering": ("Engineering Methods", ["traffic engineering", "roadway design",
                                                           "highway design", "traffic studies"]),
    "Water Resources": ("Engineering Methods", ["hydrology", "hydraulics", "water distribution",
                                                "wastewater"]),
    "Surveying": ("Engineering Methods", ["land surveying", "topographic survey"]),
    "Building Codes": ("Engineering Methods", ["building code", "ibc", "international building code",
                                               "asce 7", "aci 318", "aisc"]),
    "Permitting": ("Engineering Methods", ["permit applications", "permit drawings", "permit documents"]),
    "Construction Administration": ("Engineering Methods", ["construction management",
                                                            "construction oversight",
                                                            "construction inspection"]),
    # Design Tools
    "Figma": ("Design Tools", []),
    "Sketch": ("Design Tools", []),
    "Adobe XD": ("Design Tools", []),
    "Adobe Creative Suite": ("Design Tools", ["adobe creative cloud", "photoshop", "illustrator",
                                              "indesign", "after effects"]),
    "InVision": ("Design Tools", []),
    "Axure": ("Design Tools", ["axure rp"]),
    "Miro": ("Design Tools", []),
    # Design Methods
    "Wireframing": ("Design Methods", ["wireframe", "wireframes"]),
    "Prototyping": ("Design Methods", ["prototype", "prototypes"]),
    "User Research": ("Design Methods", ["ux research", "user interviews", "usability research",
                                         "contextual inquiry"]),
    "Usability Testing": ("Design Methods", ["usability tests", "usability studies", "user testing"]),
    "Information Architecture": ("Design Methods", []),
    "Interaction Design": ("Design Methods", ["ixd"]),
    "Design Systems": ("Design Methods", ["design system", "component library", "pattern library"]),
    "User-Centered Design": ("Design Methods", ["user centered design", "user-centred design",
                                                "human-centered design", "human centered design", "ucd"]),
    "Accessibility": ("Design Methods", ["wcag", "ada compliance", "a11y", "section 508"]),
    "Personas": ("Design Methods", ["persona", "user personas"]),
    "User Journey Mapping": ("Design Methods", ["journey map", "journey maps", "journey mapping",
                                                "user journeys", "user flows", "customer journey"]),
    "Visual Design": ("Design Methods", ["ui design", "typography", "color theory"]),
    "Responsive Design": ("Design Methods", ["responsive web design", "mobile-first"]),
    "Design Thinking": ("Design Methods", []),
    # Business Analysis
    "Requirements Gathering": ("Business Analysis", ["requirements elicitation", "requirements analysis",
                                                     "business requirements", "gather requirements",
                                                     "requirements definition"]),
    "User Stories": ("Business Analysis", ["user story", "acceptance criteria"]),
    "Process Mapping": ("Business Analysis", ["process modeling", "process modelling", "bpmn",
                                              "process flows", "business process modeling"]),
    "Process Improvement": ("Business Analysis", ["business process improvement", "process optimization",
                                                  "continuous improvement"]),
    "Gap Analysis": ("Business Analysis", []),
    "UAT": ("Business Analysis", ["user acceptance testing"]),
    "Stakeholder Management": ("Business Analysis", ["stakeholder engagement", "manage stakeholders",
                                                     "stakeholder communication"]),
    "Data Analysis": ("Business Analysis", ["data analytics", "analyze data", "analyse data",
                                            "analyzing data"]),
    "Documentation": ("Business Analysis", ["technical documentation", "technical writing"]),
    "Cost-Benefit Analysis": ("Business Analysis", ["cost benefit analysis", "business case",
                                                    "business cases", "roi analysis"]),
    "KPIs": ("Business Analysis", ["kpi", "key performance indicators", "key performance indicator"]),
    "Change Management": ("Business Analysis", ["organizational change"]),
    "Backlog Management": ("Business Analysis", ["product backlog", "backlog grooming",
                                                 "backlog refinement", "backlog"]),
    # Business Software
    "Visio": ("Business Software", ["microsoft visio", "ms visio"]),
    "Jira": ("Business Software", ["atlassian jira"]),
    "Confluence": ("Business Software", []),
    "SharePoint": ("Business Software", []),
    "Microsoft Office": ("Business Software", ["ms office", "office 365", "microsoft 365", "m365"]),
    "ERP": ("Business Software", ["sap", "oracle erp", "netsuite", "erp systems"]),
    "Salesforce": ("Business Software", ["sfdc"]),
    "CRM": ("Business Software", ["customer relationship management"]),
    "MS Project": ("Business Software", ["microsoft project"]),
    "Primavera P6": ("Business Software", ["primavera"]),
    "Smartsheet": ("Business Software", []),
    "Asana": ("Business Software", []),
    # Project Management
    "Agile": ("Project Management", ["agile methodology", "agile methodologies", "agile development"]),
    "Scrum": ("Project Management", ["scrum master", "sprint planning"]),
    "Waterfall": ("Project Management", ["waterfall methodology"]),
    "Kanban": ("Project Management", []),
    "Risk Management": ("Project Management", ["risk assessment", "risk assessments", "risk analysis",
                                               "risk mitigation"]),
    "Budget Management": ("Project Management", ["budgeting", "budget tracking", "managing budgets",
                                                 "cost control"]),
    "Scheduling": ("Project Management", ["project scheduling", "project schedules", "schedule management",
                                          "critical path"]),
    "Resource Allocation": ("Project Management", ["resource management", "resource planning"]),
    "Scope Management": ("Project Management", ["project scope", "scope definition"]),
    "Vendor Management": ("Project Management", ["vendor relationships", "supplier management",
                                                 "contract management"]),
    "Quality Management": ("Project Management", ["quality assurance", "quality control", "qa/qc"]),
    "Status Reporting": ("Project Management", ["status reports", "project reporting"]),
    "Cost Estimation": ("Project Management", ["cost estimating", "cost estimates", "quantity takeoff",
                                               "quantity takeoffs"]),
    # Certifications
    "Security+": ("Certifications", ["comptia security+"]),
    "CISSP": ("Certifications", []),
    "CEH": ("Certifications", ["certified ethical hacker"]),
    "CISM": ("Certifications", []),
    "CCNA": ("Certifications", []),
    "CCNP": ("Certifications", []),
    "Cloud Certifications": ("Certifications", ["aws certified", "aws certification", "azure certified",
                                                "azure certification", "az-104", "az-900",
                                                "google cloud certified"]),
    "PE License": ("Certifications", ["professional engineer", "p.e. license", "licensed pe",
                                      "pe license", "p.e."]),
    "EIT/FE": ("Certifications", ["eit", "engineer in training", "engineer-in-training", "fe exam",
                                  "fundamentals of engineering"]),
    "PMP": ("Certifications", ["project management professional"]),
    "PRINCE2": ("Certifications", ["prince 2"]),
    # Soft Skills
    "Communication": ("Soft Skills", ["communication skills", "verbal communication",
                                      "written communication", "communicate effectively"]),
    "Teamwork": ("Soft Skills", ["collaboration", "team player", "collaborate"]),
    "Problem Solving": ("Soft Skills", ["problem-solving", "problem solver", "critical thinking",
                                        "analytical thinking"]),
    "Leadership": ("Soft Skills", ["team leadership", "leadership skills"]),
    "Attention to Detail": ("Soft Skills", ["detail-oriented", "detail oriented", "meticulous"]),
    "Time Management": ("Soft Skills", ["prioritization", "multitasking", "multi-tasking"]),
    "Presentation Skills": ("Soft Skills", ["presenting", "presentations", "public speaking"]),
    "Negotiation": ("Soft Skills", ["negotiating", "negotiate"]),
}

# ---------------------------------------------------------------------------
# 3. Ambiguous short tokens: matched CASE-SENSITIVELY as standalone tokens.
# If a list of context words is given, one of them must appear within
# CONTEXT_WINDOW characters of the token (needed for single letters and "Go").
# Skills listed here get ambiguous=true in skills.csv.
# ---------------------------------------------------------------------------
CONTEXT_WINDOW = 60
PROG_CONTEXT = ["python", "java", "sql", "programming", "language", "languages", "coding"]
AMBIGUOUS_TOKENS: dict[str, dict[str, list[str] | None]] = {
    "R": {"R": PROG_CONTEXT + ["sas", "spss", "stata", "matlab", "scala", "julia", "statistical",
                               "statistics", "tidyverse", "ggplot2", "shiny"]},
    "C": {"C": PROG_CONTEXT + ["c++", "c#", "embedded", "firmware", "assembly", "rust",
                               "microcontroller", "microcontrollers", "verilog", "vhdl"]},
    "Go": {"Go": PROG_CONTEXT + ["golang", "rust", "kotlin", "c++", "ruby", "scala", "node.js",
                                 "typescript", "microservices", "backend"]},
    "Incident Response": {"IR": None},
    "Machine Learning": {"ML": None},
    "SAS": {"SAS": None},
    "Excel": {"Excel": None},
    "Apache Spark": {"Spark": None},
    "React": {"React": None},
    "Sketch": {"Sketch": None},
    "IDS/IPS": {"IDS": None, "IPS": None},
}

# ---------------------------------------------------------------------------
# 4. Which skills belong to which role (25-30 each, max 8 categories per role)
# ---------------------------------------------------------------------------
ROLE_SKILLS: dict[str, list[str]] = {
    "Data Analyst": [
        "SQL", "Python", "R", "Excel", "Tableau", "Power BI", "Looker", "Qlik", "Data Visualisation",
        "Statistics", "Regression Analysis", "A/B Testing", "Predictive Modeling", "Machine Learning",
        "ETL", "Data Warehousing", "Data Cleaning", "Data Modeling", "Snowflake", "SAS", "SPSS",
        "Google Analytics", "Apache Spark", "Data Analysis", "KPIs",
        "Communication", "Attention to Detail", "Problem Solving", "Presentation Skills",
    ],
    "Cybersecurity Analyst": [
        "SIEM", "Incident Response", "Vulnerability Management", "Penetration Testing", "Firewalls",
        "IDS/IPS", "Threat Intelligence", "Endpoint Security", "Identity and Access Management",
        "Encryption", "Network Security", "Cloud Security", "Digital Forensics", "Malware Analysis",
        "NIST", "ISO 27001", "Security Compliance", "Active Directory", "Risk Management",
        "Security+", "CISSP", "CEH", "CISM", "Python", "PowerShell", "Linux", "TCP/IP", "Wireshark",
        "Communication", "Problem Solving",
    ],
    "Software Engineer": [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go", ".NET", "SQL", "HTML",
        "CSS", "React", "Node.js", "REST APIs", "Microservices", "Unit Testing",
        "Object-Oriented Programming", "Data Structures & Algorithms", "System Design", "Git",
        "Docker", "Kubernetes", "AWS", "CI/CD", "Linux", "Agile", "NoSQL",
        "Problem Solving", "Communication",
    ],
    "Data Scientist": [
        "Python", "R", "SQL", "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
        "Generative AI", "Statistics", "Regression Analysis", "A/B Testing", "Predictive Modeling",
        "Time Series Analysis", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch",
        "Apache Spark", "Databricks", "Jupyter", "Tableau", "Data Visualisation", "AWS", "MLOps",
        "Git", "Docker", "Communication", "Problem Solving",
    ],
    "Network Engineer": [
        "TCP/IP", "Routing and Switching", "BGP", "OSPF", "Cisco", "Juniper", "VLAN", "VPN", "DNS",
        "DHCP", "LAN/WAN", "SD-WAN", "Load Balancing", "Wireless Networking", "Network Monitoring",
        "Wireshark", "QoS", "MPLS", "Network Automation", "Troubleshooting", "Cloud Networking",
        "Firewalls", "Network Security", "CCNA", "CCNP", "Python", "Linux", "Ansible",
        "Communication",
    ],
    "Cloud Engineer": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "CI/CD",
        "Infrastructure as Code", "Serverless", "Monitoring Tools", "Linux", "Cloud Cost Optimization",
        "Git", "Microservices", "REST APIs", "Python", "Bash", "PowerShell", "Go", "Cloud Security",
        "Identity and Access Management", "Cloud Networking", "DNS", "Load Balancing",
        "Cloud Certifications", "Agile", "Problem Solving", "Communication",
    ],
    "Electrical Engineer": [
        "AutoCAD", "CAD", "MATLAB", "Simulink", "PCB Design", "PLC", "SCADA", "Revit",
        "Circuit Design", "Power Systems Analysis", "Power Distribution", "Substation Design", "NEC",
        "Lighting Design", "Motor Controls", "Control Systems", "Embedded Systems", "Instrumentation",
        "Commissioning", "Engineering Drawings", "MEP", "PE License", "EIT/FE", "Python", "C",
        "Microsoft Office", "Communication", "Problem Solving",
    ],
    "Mechanical Engineer": [
        "SolidWorks", "AutoCAD", "CAD", "CATIA", "Creo", "Siemens NX", "ANSYS", "FEA", "CFD", "MATLAB",
        "GD&T", "Tolerance Analysis", "DFM", "FMEA", "Thermal Analysis", "HVAC", "MEP",
        "Lean Six Sigma", "Root Cause Analysis", "Engineering Drawings", "Commissioning",
        "Materials Selection", "Manufacturing Processes", "Prototyping", "PE License", "Python",
        "Microsoft Office", "Communication", "Problem Solving",
    ],
    "Civil Engineer": [
        "AutoCAD", "Civil 3D", "MicroStation", "Revit", "BIM", "GIS", "Structural Analysis Software",
        "Hydraulic Modeling", "Bluebeam", "Structural Design", "Geotechnical Engineering",
        "Stormwater Management", "Site Design & Grading", "Transportation Engineering",
        "Water Resources", "Surveying", "Building Codes", "Permitting", "Construction Administration",
        "Engineering Drawings", "Cost Estimation", "Scheduling", "PE License", "EIT/FE",
        "Microsoft Office", "Communication", "Problem Solving", "Attention to Detail",
    ],
    "UI/UX Designer": [
        "Figma", "Sketch", "Adobe XD", "Adobe Creative Suite", "InVision", "Axure", "Miro",
        "Wireframing", "Prototyping", "User Research", "Usability Testing", "Information Architecture",
        "Interaction Design", "Design Systems", "User-Centered Design", "Accessibility", "Personas",
        "User Journey Mapping", "Visual Design", "Responsive Design", "Design Thinking",
        "HTML", "CSS", "JavaScript", "A/B Testing", "Agile",
        "Communication", "Teamwork", "Presentation Skills",
    ],
    "Business Analyst": [
        "Requirements Gathering", "User Stories", "Process Mapping", "Process Improvement",
        "Gap Analysis", "UAT", "Stakeholder Management", "Data Analysis", "Documentation",
        "Cost-Benefit Analysis", "KPIs", "Change Management", "Backlog Management",
        "SQL", "Excel", "Tableau", "Power BI", "Visio", "Jira", "Confluence", "SharePoint", "ERP",
        "Salesforce", "CRM", "Agile", "Scrum", "Communication", "Problem Solving", "Presentation Skills",
    ],
    "Project Manager": [
        "Agile", "Scrum", "Waterfall", "Kanban", "Risk Management", "Budget Management", "Scheduling",
        "Resource Allocation", "Scope Management", "Vendor Management", "Quality Management",
        "Status Reporting", "Cost Estimation", "PMP", "PRINCE2", "MS Project", "Primavera P6",
        "Smartsheet", "Asana", "Jira", "Confluence", "Microsoft Office", "Stakeholder Management",
        "Change Management", "Requirements Gathering", "Construction Administration",
        "Communication", "Leadership", "Negotiation", "Time Management",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def phrase_regex(term: str) -> str:
    """Whole word/phrase pattern. (?<!\\w) and (?!\\w) behave like \\b...\\b for normal
    words, and also work for terms that start/end with symbols (C++, C#, .NET, Security+).
    Spaces in a phrase match any run of whitespace (descriptions contain line breaks)."""
    body = re.escape(term).replace(r"\ ", r"\s+")
    return rf"(?<!\w){body}(?!\w)"


def strict_token_regex(token: str) -> str:
    """Case-sensitive standalone token for ambiguous short skills.
    Not allowed to be glued to letters/digits or to & - . + # (stops R&D, Objective-C,
    C++ counting as C, Go-to-market, R.N.). "Python/R" and "C/C++" are still allowed."""
    return rf"(?<![\w&\-.]){re.escape(token)}(?![\w&+#\-]|\.\w|/\d)"


class SkillMatcher:
    def __init__(self, skill: str, synonyms: list[str]):
        self.skill = skill
        strict = AMBIGUOUS_TOKENS.get(skill, {})
        terms = sorted({skill, *synonyms}, key=len, reverse=True)
        loose = [t for t in terms if t not in strict]
        self.loose = re.compile("|".join(phrase_regex(t) for t in loose), re.IGNORECASE) if loose else None
        self.strict = []
        for token, context in strict.items():
            ctx = None
            if context:
                ctx = re.compile("|".join(phrase_regex(c) for c in context), re.IGNORECASE)
            self.strict.append((re.compile(strict_token_regex(token)), ctx))

    def first_match(self, text: str):
        """Return (start, end) of the first valid match, or None."""
        best = None
        if self.loose:
            m = self.loose.search(text)
            if m:
                best = (m.start(), m.end())
        for token_re, ctx in self.strict:
            for m in token_re.finditer(text):
                if best and m.start() >= best[0]:
                    break
                if ctx is None or ctx.search(text[max(0, m.start() - CONTEXT_WINDOW): m.end() + CONTEXT_WINDOW]):
                    best = (m.start(), m.end())
                    break
        return best


def build_role_regex() -> dict[str, re.Pattern]:
    return {role: re.compile("|".join(phrase_regex(k) for k in kws)) for role, kws in ROLE_KEYWORDS.items()}


EXCLUDE_RE = re.compile("|".join(phrase_regex(k) for k in TITLE_EXCLUDE))

# Extra exclusions for a single role (e.g. "Salesforce Commerce Cloud Developer" is CRM work, not cloud infra).
ROLE_EXCLUDE: dict[str, list[str]] = {
    "Cloud Engineer": ["salesforce"],
}
ROLE_EXCLUDE_RE = {r: re.compile("|".join(phrase_regex(k) for k in kws)) for r, kws in ROLE_EXCLUDE.items()}


def assign_role(title: str, role_res: dict[str, re.Pattern]) -> str | None:
    t = " ".join(str(title).lower().split())
    if EXCLUDE_RE.search(t):
        return None
    for role, rx in role_res.items():
        if role in ROLE_EXCLUDE_RE and ROLE_EXCLUDE_RE[role].search(t):
            continue
        if rx.search(t):
            return role
    return None


def check_dictionary() -> None:
    for role, skills in ROLE_SKILLS.items():
        missing = [s for s in skills if s not in SKILLS]
        assert not missing, f"{role}: skills not in dictionary: {missing}"
        assert len(skills) == len(set(skills)), f"{role}: duplicate skills"
        assert 25 <= len(skills) <= 30, f"{role}: has {len(skills)} skills"
        cats = {SKILLS[s][0] for s in skills}
        assert len(cats) <= 8, f"{role}: {len(cats)} categories"
    for skill, (_, syns) in SKILLS.items():
        for term in [skill, *syns]:
            assert "," not in term and ";" not in term, f"bad character in {term!r}"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def load_postings(raw: Path) -> tuple[pd.DataFrame, dict]:
    # Only these 4 columns are read. Company names, URLs, contact details etc. are never loaded.
    df = pd.read_csv(raw, usecols=["title", "description", "listed_time", "location"])
    stats = {"rows_raw": len(df)}
    df = df.dropna(subset=["title", "description"])
    stats["rows_with_text"] = len(df)
    df = df.drop_duplicates(subset=["title", "description"])
    stats["rows_after_dedup"] = len(df)
    df["date"] = pd.to_datetime(df["listed_time"], unit="ms")
    role_res = build_role_regex()
    df["role"] = df["title"].map(lambda t: assign_role(t, role_res))
    df = df[df["role"].notna()].reset_index(drop=True)
    stats["rows_assigned"] = len(df)
    return df, stats


def role_counts(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["role"].value_counts().reindex(list(ROLE_KEYWORDS), fill_value=0)
    out = counts.rename("postings").to_frame()
    out["flag"] = ["NONE (left out)" if n == 0 else "low sample" if n < LOW_SAMPLE_LIMIT else ""
                   for n in out["postings"]]
    return out


def count_skills(df: pd.DataFrame):
    matchers = {s: SkillMatcher(s, SKILLS[s][1]) for s in SKILLS}
    rows, matches = [], []
    for role, skills in ROLE_SKILLS.items():
        sub = df[df["role"] == role]
        total = len(sub)
        if total == 0:
            continue
        for skill in skills:
            n = 0
            for idx, text in zip(sub.index, sub["description"]):
                span = matchers[skill].first_match(text)
                if span:
                    n += 1
                    matches.append((role, skill, idx, span))
            rows.append({"role": role, "skill": skill, "demand": round(n / total, 3),
                         "postings_count": n, "total_postings": total})
    demand = pd.DataFrame(rows)
    demand["_order"] = demand["role"].map({r: i for i, r in enumerate(ROLE_KEYWORDS)})
    demand = demand.sort_values(["_order", "postings_count", "skill"], ascending=[True, False, True])
    return demand.drop(columns="_order"), matches


def write_outputs(df: pd.DataFrame, demand: pd.DataFrame, counts: pd.DataFrame, stats: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    used = sorted({s for skills in ROLE_SKILLS.values() for s in skills})
    skills_df = pd.DataFrame({
        "skill": used,
        "category": [SKILLS[s][0] for s in used],
        "synonyms": [";".join(SKILLS[s][1]) for s in used],
        "ambiguous": ["true" if s in AMBIGUOUS_TOKENS else "false" for s in used],
    })
    skills_df.to_csv(OUT_DIR / "skills.csv", index=False, encoding="utf-8", lineterminator="\n")
    demand.to_csv(OUT_DIR / "role_skill_demand.csv", index=False, encoding="utf-8",
                  lineterminator="\n", float_format="%.3f")

    roles = [r for r in ROLE_KEYWORDS if counts.loc[r, "postings"] > 0]
    low = [f"{r} ({counts.loc[r, 'postings']})" for r in roles if counts.loc[r, "postings"] < LOW_SAMPLE_LIMIT]
    missing = [r for r in ROLE_KEYWORDS if counts.loc[r, "postings"] == 0]
    notes = [
        "No Malaysian postings exist in this dataset (0 found); region set to Global as agreed with the team, "
        "but almost all postings are in the United States, so demand reflects the US job market.",
        "Only English-language LinkedIn ads posted online, mostly listed in April 2024 (a 4-week snapshot).",
        "Exact duplicates (same title + description) removed; near-duplicates and reposts may remain.",
        "Roles assigned by title keywords only (one role per posting); see DATA_README.md for the keywords.",
        "Skills counted by whole-word keyword matching in the description; a mention does not always mean "
        "a requirement (e.g. 'nice to have', company boilerplate).",
        f"Low-sample roles (<{LOW_SAMPLE_LIMIT} postings): {', '.join(low) if low else 'none'}.",
        f"Roles left out (0 postings): {', '.join(missing) if missing else 'none'}.",
        "Derived from a CC BY-SA 4.0 dataset: give attribution and share these derived files under CC BY-SA 4.0.",
    ]
    source = {
        "name": "LinkedIn Job Postings (2023 - 2024)",
        "url": "https://www.kaggle.com/datasets/arshkon/linkedin-job-postings",
        "licence": "CC BY-SA 4.0",
        "collection_method": "public licensed dataset",
        "date_range": f"{df['date'].min():%Y-%m} to {df['date'].max():%Y-%m}",
        "region": "Global",
        "postings_used": int(len(df)),
        "roles": roles,
        "notes": " ".join(notes),
    }
    (OUT_DIR / "data_source.json").write_text(json.dumps(source, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    print(f"Wrote {OUT_DIR}/skills.csv ({len(skills_df)} skills), "
          f"{OUT_DIR}/role_skill_demand.csv ({len(demand)} rows), {OUT_DIR}/data_source.json")


def print_hand_check(df: pd.DataFrame, matches: list, n: int, seed: int = 42) -> None:
    rng = random.Random(seed)
    for i, (role, skill, idx, (s, e)) in enumerate(rng.sample(matches, n), 1):
        text = df.at[idx, "description"]
        snippet = " ".join(text[max(0, s - 90): e + 90].split())
        print(f"\n[{i}] role={role} | skill={skill} | matched='{text[s:e]}'\n    ...{snippet}...")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="postings.csv", help="path to Kaggle postings.csv")
    ap.add_argument("--counts-only", action="store_true")
    ap.add_argument("--hand-check", type=int, default=0, help="print N random matches")
    ap.add_argument("--show-titles", type=int, default=0, help="print top N titles per role")
    args = ap.parse_args()

    check_dictionary()
    df, stats = load_postings(Path(args.raw))
    print("Rows:", stats)
    counts = role_counts(df)
    print("\nPostings per role:\n", counts.to_string())
    if args.show_titles:
        for role in ROLE_KEYWORDS:
            print(f"\n== {role}")
            print(df.loc[df["role"] == role, "title"].str.lower().value_counts().head(args.show_titles).to_string())
    if args.counts_only:
        return
    demand, matches = count_skills(df)
    write_outputs(df, demand, counts, stats)
    if args.hand_check:
        print_hand_check(df, matches, args.hand_check)


if __name__ == "__main__":
    main()
