import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Code2,
  ListFilter,
  CheckSquare,
  Binary,
  AlignLeft,
  Database,
  X,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { QuestionType } from '../../types/question';

interface CreateQuestionModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface QuestionTypeCard {
  type: QuestionType;
  title: string;
  subtitle: string;
  description: string;
  icon: React.ReactNode;
  accentColor: string;
  badge: string;
}

const SUPPORTED_TYPES: QuestionTypeCard[] = [
  {
    type: 'CODING',
    title: 'Coding Question',
    subtitle: 'Algorithms & Data Structures',
    description: 'Multi-language algorithmic problems with sandboxed automated test cases in Python, C++, or Java.',
    icon: <Code2 className="w-6 h-6 text-emerald-600" />,
    accentColor: 'border-emerald-200 hover:border-emerald-500 hover:bg-emerald-50/50',
    badge: 'Automated Sandbox',
  },
  {
    type: 'MCQ',
    title: 'Multiple Choice (MCQ)',
    subtitle: 'Single Answer',
    description: 'Standard multiple choice question with a single authoritative correct option and optional penalty points.',
    icon: <ListFilter className="w-6 h-6 text-purple-600" />,
    accentColor: 'border-purple-200 hover:border-purple-500 hover:bg-purple-50/50',
    badge: 'Single Choice',
  },
  {
    type: 'MULTI_SELECT',
    title: 'Multiple Select',
    subtitle: 'Multiple Answers',
    description: 'Candidates select all applicable answers from options with partial scoring or exact-match credit.',
    icon: <CheckSquare className="w-6 h-6 text-blue-600" />,
    accentColor: 'border-blue-200 hover:border-blue-500 hover:bg-blue-50/50',
    badge: 'Multi-Choice',
  },
  {
    type: 'TRUE_FALSE',
    title: 'True / False',
    subtitle: 'Binary Choice',
    description: 'Rapid conceptual verification with true or false assertion evaluation.',
    icon: <Binary className="w-6 h-6 text-teal-600" />,
    accentColor: 'border-teal-200 hover:border-teal-500 hover:bg-teal-50/50',
    badge: 'Binary',
  },
  {
    type: 'SHORT_ANSWER',
    title: 'Short Answer',
    subtitle: 'Text Tokens',
    description: 'Direct candidate text input with automated normalization for case sensitivity and whitespace.',
    icon: <AlignLeft className="w-6 h-6 text-amber-600" />,
    accentColor: 'border-amber-200 hover:border-amber-500 hover:bg-amber-50/50',
    badge: 'Token Match',
  },
  {
    type: 'SQL',
    title: 'SQL Query Question',
    subtitle: 'Database Querying',
    description: 'Relational database schema evaluation with MySQL table setups and expected query output matching.',
    icon: <Database className="w-6 h-6 text-cyan-600" />,
    accentColor: 'border-cyan-200 hover:border-cyan-500 hover:bg-cyan-50/50',
    badge: 'Relational DB',
  },
];

export const CreateQuestionModal: React.FC<CreateQuestionModalProps> = ({
  isOpen,
  onClose,
}) => {
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleSelectType = (type: QuestionType) => {
    onClose();
    navigate(`/admin/questions/create?type=${type}`);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-question-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-3xl w-full overflow-hidden text-slate-900">
        {/* Header */}
        <div className="px-8 py-6 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono font-semibold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Step 1 of Authoring</span>
            </div>
            <h2 id="create-question-modal-title" className="text-xl font-extrabold tracking-tight">
              Select Question Type
            </h2>
            <p className="text-xs text-slate-300">
              Choose from the 6 supported assessment question architectures to begin authoring.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-white/10 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Type Cards Grid */}
        <div className="p-8 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {SUPPORTED_TYPES.map((card) => (
              <button
                key={card.type}
                type="button"
                onClick={() => handleSelectType(card.type)}
                className={`text-left p-5 rounded-2xl border-2 transition-all duration-200 flex flex-col justify-between group ${card.accentColor} bg-white hover:shadow-md cursor-pointer`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 group-hover:scale-105 transition-transform">
                      {card.icon}
                    </div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                      {card.badge}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                    {card.title}
                  </h3>
                  <p className="text-xs font-semibold text-slate-600 mb-1.5 font-mono">
                    {card.subtitle}
                  </p>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {card.description}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-slate-500 group-hover:text-emerald-700">
                  <span>Start Authoring</span>
                  <ArrowRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
