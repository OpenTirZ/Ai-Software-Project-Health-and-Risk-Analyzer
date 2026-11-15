export type PageView =
  | 'login'
  | 'signup'
  | 'projects'
  | 'create-project'
  | 'connect-repo'
  | 'overview'
  | 'health-analysis'
  | 'risk-analysis'
  | 'contributors'
  | 'activity'
  | 'reports'
  | 'profile';

export interface UserProfileData {
  id?: string;
  fullName: string;
  username: string;
  email: string;
  role?: string;
  team?: string;
  bio?: string;
}

export type ActivityTab = 'commits' | 'pull-requests' | 'issues';

export interface Repository {
  id: string;
  name: string;
  branch: string;
  healthScore: number;
  riskClassification: 'LOW RISK' | 'ELEVATED CHURN' | 'HIGH RISK' | 'MODERATE CHURN';
  lastAudit: string;
  description?: string;
  monitored?: boolean;
}

export interface Contributor {
  id: string;
  name: string;
  username: string;
  commits: number;
  lastActive: string;
  avatarUrl?: string;
}

export interface CommitItem {
  id: string;
  hash: string;
  message: string;
  author: string;
  date: string;
  files: number;
}

export interface PullRequestItem {
  id: string;
  prNumber: number;
  title: string;
  author: string;
  age: string;
  status: 'Open' | 'Merged' | 'Closed';
}

export interface IssueItem {
  id: string;
  issueNumber: number;
  title: string;
  author: string;
  priority: 'High' | 'Medium' | 'Low';
  status: 'Open' | 'Closed';
  updated: string;
}

export interface RiskItem {
  id: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  description: string;
  evidence: string[];
  threshold: string;
  whyRisk?: string;
}

export interface ReportItem {
  id: string;
  title: string;
  project: string;
  generatedDate: string;
  healthScore: number;
  risksCount: number;
  bottlenecksCount: number;
  recommendations: string[];
}
