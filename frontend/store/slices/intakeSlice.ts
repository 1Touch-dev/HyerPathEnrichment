import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { EnrichMode, EnrichmentInput } from '@/src/lib/types';

const emptyDraft = (): EnrichmentInput => ({
  email: '',
  linkedinUrl: '',
  username: '',
  company: '',
  business: '',
  jobSearch: '',
  // Default depth matches the Figma "Standard" preset.
  requestedTiers: ['tier2', 'tier3'],
});

type IntakeState = {
  draft: EnrichmentInput;
  enrichMode: EnrichMode;
};

const initialState: IntakeState = {
  draft: emptyDraft(),
  enrichMode: 'async',
};

const intakeSlice = createSlice({
  name: 'intake',
  initialState,
  reducers: {
    setDraft(state, action: PayloadAction<EnrichmentInput>) {
      state.draft = action.payload;
    },
    patchDraft(state, action: PayloadAction<Partial<EnrichmentInput>>) {
      state.draft = { ...state.draft, ...action.payload };
    },
    resetDraft(state) {
      state.draft = emptyDraft();
    },
    setEnrichMode(state, action: PayloadAction<EnrichMode>) {
      state.enrichMode = action.payload;
    },
  },
});

export const { setDraft, patchDraft, resetDraft, setEnrichMode } = intakeSlice.actions;
export default intakeSlice.reducer;
