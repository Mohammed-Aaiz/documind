import type { WorkspaceMode, WorkspaceTask } from '../../types';

export interface WorkspaceAction { task: WorkspaceTask; title: string; description: string; prompt: string; icon: string }
export const WORKSPACES: Record<WorkspaceMode, { label: string; eyebrow: string; title: string; description: string; icon: string; actions: WorkspaceAction[] }> = {
  student: {
    label: 'Student', eyebrow: 'A little clarity. A lot of possibility.', title: 'Make sense of what you study.',
    description: 'Bring your course materials. Build clear answers, explore difficult ideas, and prepare with the evidence beside you.', icon: 'school',
    actions: [
      { task: 'answer', title: 'Build an exam answer', description: 'Choose 5, 10, or 15 marks.', prompt: 'Explain the main concept in my documents, with the essential points and supporting evidence.', icon: 'edit_note' },
      { task: 'explain', title: 'Untangle a concept', description: 'Step through a difficult idea.', prompt: 'Explain the most important concept in these documents step by step, using only examples supported by the sources.', icon: 'lightbulb' },
      { task: 'revision', title: 'Create revision notes', description: 'Key concepts, clearly organised.', prompt: 'Create concise revision notes from these documents. Group key concepts and cite the supporting passages.', icon: 'sticky_note_2' },
      { task: 'practice', title: 'Practice what you know', description: 'Questions grounded in your notes.', prompt: 'Create practice questions and a separate answer guide from my documents, with citations for each answer.', icon: 'quiz' },
    ],
  },
  research: {
    label: 'Research', eyebrow: 'Follow the evidence. Find your perspective.', title: 'Connect ideas. Question assumptions.',
    description: 'Explore your source collection, compare perspectives, and build a traceable argument from the material you trust.', icon: 'biotech',
    actions: [
      { task: 'synthesis', title: 'Synthesize sources', description: 'Find the themes across your reading.', prompt: 'Synthesize the main themes across my documents. Distinguish agreement from differences and cite each source.', icon: 'hub' },
      { task: 'comparison', title: 'Compare perspectives', description: 'Methods, findings, and trade-offs.', prompt: 'Compare the methods and findings in my documents. Attribute each point to its source and identify limitations.', icon: 'compare_arrows' },
      { task: 'critique', title: 'Examine the argument', description: 'Claims, evidence, and limitations.', prompt: 'Critically appraise the claims in my documents. Separate stated evidence, assumptions, and limitations without inventing facts.', icon: 'fact_check' },
      { task: 'gaps', title: 'Explore open questions', description: 'What this collection does not answer.', prompt: 'Identify questions left unanswered by this source collection. Frame them as possible research directions, not proven gaps in the entire literature.', icon: 'travel_explore' },
    ],
  },
};
