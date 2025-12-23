# PSIRT Analyzer - Frontend

Modern React web interface for PSIRT vulnerability analysis and device verification.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **React Query** - API state management
- **Axios** - HTTP client

## Features

1. **PSIRT Analysis**
   - Paste PSIRT summary text
   - Select platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
   - Get predicted labels from SEC-8B model
   - View config regex patterns and show commands

2. **Device Verification**
   - Connect to devices via SSH
   - Two-stage verification (version + feature)
   - Visual vulnerability status
   - Detailed evidence from device commands

3. **Export & Reporting**
   - Export verification results as JSON
   - Copy analysis results for documentation

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Backend API running on http://localhost:8000

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Frontend will be available at http://localhost:3000

### Build for Production

```bash
npm run build
npm run preview  # Preview production build
```

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # API client and error handling
│   ├── components/
│   │   ├── AnalyzeForm.tsx    # PSIRT analysis form
│   │   ├── ResultsDisplay.tsx # Analysis results display
│   │   ├── DeviceForm.tsx     # Device credentials form
│   │   └── VerificationReport.tsx  # Verification results
│   ├── types/
│   │   └── index.ts           # TypeScript type definitions
│   ├── styles/
│   │   └── index.css          # Global styles and Tailwind
│   ├── App.tsx                # Main app component
│   └── main.tsx               # Entry point
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## API Integration

The frontend connects to the FastAPI backend via proxy configuration in `vite.config.ts`:

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  }
}
```

### API Endpoints Used

- `POST /api/v1/analyze-psirt` - Analyze PSIRT with SEC-8B
- `POST /api/v1/verify-device` - Verify device vulnerability
- `GET /api/v1/results/{id}` - Get cached analysis results
- `GET /api/v1/health` - Health check

## Environment Variables

Create `.env.local` for custom configuration:

```bash
VITE_API_URL=http://localhost:8000/api/v1  # Override API URL
```

## Development Tips

### Hot Reload

Vite provides instant HMR (Hot Module Replacement). Changes to `.tsx` and `.css` files update immediately.

### Type Checking

```bash
npm run build  # Runs TypeScript compiler before build
```

### Linting

```bash
npm run lint
```

## Component Usage Examples

### AnalyzeForm

```tsx
import { AnalyzeForm } from './components/AnalyzeForm';

<AnalyzeForm
  onAnalyze={(summary, platform, advisoryId) => {
    // Handle analysis
  }}
  loading={false}
/>
```

### ResultsDisplay

```tsx
import { ResultsDisplay } from './components/ResultsDisplay';

<ResultsDisplay
  analysis={analysisResult}
  onVerifyDevice={() => {
    // Show device form
  }}
/>
```

### DeviceForm

```tsx
import { DeviceForm } from './components/DeviceForm';

<DeviceForm
  onVerify={(credentials, metadata) => {
    // Handle verification
  }}
  loading={false}
/>
```

### VerificationReport

```tsx
import { VerificationReport } from './components/VerificationReport';

<VerificationReport
  result={verificationResult}
  onExport={(format) => {
    // Handle export
  }}
/>
```

## State Management

Uses React Query for API state management with automatic caching, retries, and loading states:

```typescript
const analyzeMutation = useMutation({
  mutationFn: (data) => api.analyzePSIRT(data),
  onSuccess: (data) => {
    // Handle success
  },
  onError: (error) => {
    // Handle error
  },
});
```

## Styling

### Tailwind Utility Classes

Custom utilities defined in `src/styles/index.css`:

- `.card` - Card container
- `.btn-primary`, `.btn-success`, etc. - Button variants
- `.badge-primary`, `.badge-success`, etc. - Badge variants
- `.alert-error`, `.alert-success`, etc. - Alert variants
- `.spinner` - Loading spinner

### Responsive Design

All components are responsive and mobile-friendly using Tailwind's responsive utilities.

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Troubleshooting

### Backend Connection Failed

1. Ensure backend is running: `curl http://localhost:8000/api/v1/health`
2. Check proxy configuration in `vite.config.ts`
3. Check browser console for CORS errors

### Build Errors

1. Clear node_modules and reinstall: `rm -rf node_modules package-lock.json && npm install`
2. Check TypeScript errors: `npm run build`

## Performance

- Initial load: ~200KB (gzipped)
- Lazy loading for large components
- React Query caching for API responses
- Vite optimized production builds

## Security

- Credentials never stored in localStorage
- HTTPS required for production
- CORS configured in backend
- Input validation on all forms
- XSS protection via React's built-in escaping

## License

Part of the PSIRT Analysis project.
