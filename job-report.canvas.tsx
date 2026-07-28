import { useEffect, useState } from 'react';

interface JobReport {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  dossier: {
    photo?: { source: string; assetUrl: string; capturedAt: string; confidence: number };
    handles: Array<{ platform: string; username: string; profileUrl: string; confidence: number }>;
    emails: string[];
    verified_emails: Array<{ value: string; status: string; confidence: number; source: string }>;
    github?: { profile?: string; organizations: string[]; publicCommits: number };
    coworkers: string[];
    jobs: Array<{ title: string; company: string; location: string; remote: boolean; source: string }>;
    business?: { name: string; address: string; website: string; rating: number; phone: string };
    confidence: Array<{ label: string; score: number; evidence: string[] }>;
    sources: string[];
    metadata: any;
  };
  error?: string;
  progress_metadata?: any;
}

export default function JobReportCanvas() {
  const [job, setJob] = useState<JobReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const jobId = 'job_cf61568928174d5d946758e6ff5cc31a';

  useEffect(() => {
    fetch(`/api/enrich/${jobId}`)
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setJob(data.data);
        } else {
          setError(data.error?.message || 'Failed to fetch job');
        }
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading job report...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-red-800 font-semibold text-lg mb-2">Error</h2>
          <p className="text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      completed: 'bg-green-100 text-green-800 border-green-200',
      running: 'bg-blue-100 text-blue-800 border-blue-200',
      queued: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      failed: 'bg-red-100 text-red-800 border-red-200',
      completed_no_data: 'bg-gray-100 text-gray-800 border-gray-200',
      suppressed: 'bg-purple-100 text-purple-800 border-purple-200',
    };
    return colors[status] || 'bg-gray-100 text-gray-800 border-gray-200';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Enrichment Job Report</h1>
              <p className="text-gray-500 font-mono text-sm">{job.id}</p>
            </div>
            <span className={`px-4 py-2 rounded-full text-sm font-semibold border ${getStatusColor(job.status)}`}>
              {job.status.replace('_', ' ').toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-gray-200">
            <div>
              <p className="text-sm text-gray-500 mb-1">Created At</p>
              <p className="text-gray-900 font-medium">{new Date(job.created_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500 mb-1">Updated At</p>
              <p className="text-gray-900 font-medium">{new Date(job.updated_at).toLocaleString()}</p>
            </div>
          </div>
        </div>

        {/* Photo Section */}
        {job.dossier.photo && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">📸</span> Profile Photo
            </h2>
            <div className="flex items-start gap-6">
              <img
                src={job.dossier.photo.assetUrl}
                alt="Profile"
                className="w-32 h-32 rounded-lg object-cover border-2 border-gray-200 shadow-md"
              />
              <div className="flex-1">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Source</p>
                    <p className="text-gray-900 font-medium">{job.dossier.photo.source}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Confidence</p>
                    <p className="text-gray-900 font-medium">{(job.dossier.photo.confidence * 100).toFixed(0)}%</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-sm text-gray-500 mb-1">Captured At</p>
                    <p className="text-gray-900 font-medium">{new Date(job.dossier.photo.capturedAt).toLocaleString()}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Social Handles */}
        {job.dossier.handles.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">🔗</span> Social Media Handles ({job.dossier.handles.length})
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {job.dossier.handles.map((handle, idx) => (
                <div key={idx} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-gray-900 capitalize">{handle.platform}</span>
                    <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full">
                      {(handle.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  <p className="text-gray-700 mb-1">@{handle.username}</p>
                  <a
                    href={handle.profileUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm break-all"
                  >
                    {handle.profileUrl}
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Emails */}
        {(job.dossier.emails.length > 0 || job.dossier.verified_emails.length > 0) && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">📧</span> Email Addresses
            </h2>

            {job.dossier.verified_emails.length > 0 && (
              <div className="mb-4">
                <h3 className="font-semibold text-gray-700 mb-2">Verified Emails</h3>
                <div className="space-y-2">
                  {job.dossier.verified_emails.map((email, idx) => (
                    <div key={idx} className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-gray-900">{email.value}</span>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            email.status === 'verified' ? 'bg-green-100 text-green-800' :
                            email.status === 'risky' ? 'bg-orange-100 text-orange-800' :
                            email.status === 'disposable' ? 'bg-red-100 text-red-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {email.status}
                          </span>
                          <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full">
                            {(email.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">Source: {email.source}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {job.dossier.emails.length > 0 && (
              <div>
                <h3 className="font-semibold text-gray-700 mb-2">Other Emails</h3>
                <div className="flex flex-wrap gap-2">
                  {job.dossier.emails.map((email, idx) => (
                    <span key={idx} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-mono">
                      {email}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Jobs */}
        {job.dossier.jobs.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">💼</span> Job Listings ({job.dossier.jobs.length})
            </h2>
            <div className="space-y-3">
              {job.dossier.jobs.map((job, idx) => (
                <div key={idx} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-gray-900">{job.title}</h3>
                    {job.remote && (
                      <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded-full">Remote</span>
                    )}
                  </div>
                  <p className="text-gray-700 mb-1">{job.company}</p>
                  <p className="text-sm text-gray-500 mb-2">{job.location}</p>
                  <p className="text-xs text-gray-400">Source: {job.source}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* GitHub */}
        {job.dossier.github?.profile && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">👨‍💻</span> GitHub Profile
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-gray-500 mb-1">Profile</p>
                <a href={job.dossier.github.profile} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800">
                  {job.dossier.github.profile}
                </a>
              </div>
              <div>
                <p className="text-sm text-gray-500 mb-1">Organizations</p>
                <p className="text-gray-900 font-medium">{job.dossier.github.organizations.length}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500 mb-1">Public Commits</p>
                <p className="text-gray-900 font-medium">{job.dossier.github.publicCommits}</p>
              </div>
            </div>
          </div>
        )}

        {/* Confidence Breakdown */}
        {job.dossier.confidence.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">📊</span> Confidence Scores
            </h2>
            <div className="space-y-4">
              {job.dossier.confidence.map((item, idx) => (
                <div key={idx}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-gray-900">{item.label}</span>
                    <span className="text-sm font-medium text-gray-700">{(item.score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all"
                      style={{ width: `${item.score * 100}%` }}
                    ></div>
                  </div>
                  {item.evidence.length > 0 && (
                    <details className="text-sm text-gray-600">
                      <summary className="cursor-pointer hover:text-gray-900">Evidence ({item.evidence.length})</summary>
                      <ul className="mt-2 ml-4 list-disc space-y-1">
                        {item.evidence.map((ev, eidx) => (
                          <li key={eidx}>{ev}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sources */}
        {job.dossier.sources.length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              <span className="mr-2">🔍</span> Data Sources ({job.dossier.sources.length})
            </h2>
            <div className="flex flex-wrap gap-2">
              {job.dossier.sources.map((source, idx) => (
                <span key={idx} className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                  {source}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {job.error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
            <h2 className="text-xl font-bold text-red-900 mb-2 flex items-center">
              <span className="mr-2">⚠️</span> Error
            </h2>
            <p className="text-red-700">{job.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
