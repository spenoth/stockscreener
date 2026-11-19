import { Routes } from '@angular/router';
import { StockListComponent } from './components/stock-list/stock-list.component';
import { AnalyzePageComponent } from './components/analyze-page/analyze-page.component';

export const routes: Routes = [
  {
    path: '',
    component: StockListComponent
  },
  {
    path: 'analyze/:ticker',
    component: AnalyzePageComponent
  },
  {
    path: '**',
    redirectTo: ''
  }
];

