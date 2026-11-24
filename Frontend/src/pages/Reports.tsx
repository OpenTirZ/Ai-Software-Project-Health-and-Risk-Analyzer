import React from 'react';
// @ts-ignore
import ReportsComponent from './Reports.jsx';
import type { PageView } from '../types';

export interface ReportsProps {
  projectId?: string;
  selectedRepo: string;
  onNavigate: (view: PageView) => void;
}

export const Reports: React.FC<ReportsProps> = (props) => {
  return <ReportsComponent {...props} />;
};

export default Reports;
