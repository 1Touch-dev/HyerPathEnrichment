import type { ConfidenceBreakdown, Dossier, SocialHandle, VerifiedEmail } from '@/src/lib/types';

type DossierJob = Dossier['jobs'][number];

export type DossierEntity =
  | {
      kind: 'handle';
      id: string;
      title: string;
      subtitle?: string;
      confidence: number;
      entity: SocialHandle;
    }
  | {
      kind: 'verifiedEmail';
      id: string;
      title: string;
      subtitle?: string;
      confidence: number;
      entity: VerifiedEmail;
    }
  | {
      kind: 'email';
      id: string;
      title: string;
      entity: string;
    }
  | {
      kind: 'job';
      id: string;
      title: string;
      subtitle?: string;
      entity: DossierJob;
    }
  | {
      kind: 'confidence';
      id: string;
      title: string;
      subtitle?: string;
      confidence: number;
      entity: ConfidenceBreakdown;
    }
  | {
      kind: 'source';
      id: string;
      title: string;
      entity: string;
    };

