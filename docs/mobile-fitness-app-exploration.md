# Mobile Fitness App - Exploration & Feasibility Study

> Research document for evaluating a mobile fitness app as a DREAM Team managed project

## Executive Summary

This document explores the feasibility of building a mobile fitness app as a new project managed by the DREAM Team framework. The fitness app is already referenced as a flagship example in the DREAM Team architecture. This exploration covers technology choices, feature scope, architecture, and a recommended path forward.

---

## 1. Why a Mobile Fitness App?

### Market Opportunity
- Global fitness app market valued at ~$1.5B+ and growing rapidly
- Post-pandemic shift toward at-home and hybrid fitness
- Users increasingly expect AI-powered personalization
- Opportunity to differentiate with Claude-powered coaching and plan generation

### Strategic Fit with DREAM Team
- Already referenced as an example project in the DREAM Team architecture
- Demonstrates the framework's ability to manage a full mobile product lifecycle
- Cross-pollination: fitness app can leverage DREAM Team's AI capabilities for smart features

---

## 2. Recommended Tech Stack

### Option A: React Native (Recommended)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Framework** | React Native + Expo | Cross-platform (iOS + Android), large ecosystem, fast iteration |
| **Language** | TypeScript | Type safety, better DX, industry standard |
| **State Management** | Zustand or Redux Toolkit | Lightweight, scalable |
| **Navigation** | React Navigation | De facto standard for RN |
| **Backend** | FastAPI (Python) | Consistent with DREAM Team stack |
| **Database** | PostgreSQL + SQLite (local) | Server-side persistence + offline-first local storage |
| **Auth** | Supabase Auth or Firebase Auth | Battle-tested, easy social logins |
| **API** | REST + WebSocket | REST for CRUD, WebSocket for real-time features |
| **AI Integration** | Anthropic Claude API | Workout generation, coaching, form tips |

### Option B: Flutter

| Pros | Cons |
|------|------|
| Excellent performance | Dart language (smaller talent pool) |
| Beautiful UI out of the box | Less JS ecosystem integration |
| Single codebase | Heavier build tooling |

### Option C: Native (Swift + Kotlin)

| Pros | Cons |
|------|------|
| Best performance | Two codebases to maintain |
| Full platform API access | Slower development cycle |
| Best UX per platform | Higher cost, more agents needed |

**Recommendation**: React Native + Expo for fastest time-to-market with a single codebase. The DREAM Team agent can manage it as one repository.

---

## 3. Core Feature Set (MVP)

### Phase 1 - Foundation (MVP)
- [ ] User registration & profile (age, weight, height, goals)
- [ ] Workout library (pre-built routines: strength, cardio, flexibility)
- [ ] Workout logging (sets, reps, weight, duration)
- [ ] Basic workout timer / rest timer
- [ ] Exercise database with descriptions and images
- [ ] Simple progress dashboard (charts for weight, volume, streak)

### Phase 2 - Intelligence
- [ ] AI-powered workout plan generation (Claude API)
- [ ] Smart workout suggestions based on history and goals
- [ ] Natural language workout input ("I did 3 sets of 10 bench press at 135")
- [ ] Progress insights and recommendations
- [ ] Adaptive difficulty scaling

### Phase 3 - Social & Engagement
- [ ] Friend system and activity feed
- [ ] Challenges and leaderboards
- [ ] Workout sharing
- [ ] Achievement badges and streaks
- [ ] Push notifications for reminders and motivation

### Phase 4 - Advanced
- [ ] Apple Health / Google Fit integration
- [ ] Wearable device sync (heart rate, steps, calories)
- [ ] Video exercise demonstrations
- [ ] Nutrition tracking integration
- [ ] Custom workout builder with drag-and-drop

---

## 4. Proposed Architecture

```
┌─────────────────────────────────────────────┐
│            Mobile App (React Native)         │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Workout  │ │ Profile  │ │  Progress    │ │
│  │ Screens  │ │ & Auth   │ │  Dashboard   │ │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
│       └─────────────┼──────────────┘         │
│              ┌──────┴───────┐                │
│              │  API Client  │                │
│              │  + Local DB  │                │
│              └──────┬───────┘                │
└─────────────────────┼───────────────────────┘
                      │ HTTPS / WSS
                      ▼
┌─────────────────────────────────────────────┐
│           Backend API (FastAPI)              │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ │
│  │ Auth     │ │ Workout   │ │ AI Coach   │ │
│  │ Service  │ │ Service   │ │ Service    │ │
│  └──────────┘ └───────────┘ └─────┬──────┘ │
│                                    │        │
│  ┌──────────┐ ┌───────────┐ ┌─────┴──────┐ │
│  │ User     │ │ Progress  │ │ Claude API │ │
│  │ Service  │ │ Analytics │ │ Integration│ │
│  └──────────┘ └───────────┘ └────────────┘ │
│                    │                        │
│              ┌─────┴─────┐                  │
│              │ PostgreSQL │                  │
│              └───────────┘                  │
└─────────────────────────────────────────────┘
```

### Key Data Models

```
User
├── id, email, name, avatar
├── height, weight, age, gender
├── fitness_goal (lose_weight | build_muscle | endurance | general)
└── created_at, updated_at

Workout
├── id, user_id, name, type
├── scheduled_date, completed_date
├── duration_minutes, calories_burned
├── notes, ai_generated (bool)
└── exercises[] → WorkoutExercise

Exercise
├── id, name, category, muscle_groups[]
├── description, instructions
├── difficulty_level
└── equipment_required[]

WorkoutExercise
├── exercise_id, workout_id
├── sets, reps, weight, duration
├── rest_seconds, order
└── notes

ProgressEntry
├── user_id, date
├── body_weight, body_fat_pct
├── measurements{}
└── photos[]
```

---

## 5. DREAM Team Integration

### How It Fits

The fitness app would be a **managed project** within DREAM Team:

```bash
# Add the fitness app repo to DREAM Team
DREAM> add https://github.com/pg-rwa/fitness-app --name fitness-app --stack react-native,typescript,fastapi --desc "Mobile fitness tracking app with AI coaching"

# Direct the CTO to work on it
DREAM> talk Build out the workout logging feature for the fitness app
DREAM> talk Add Claude-powered workout plan generation to the fitness app
```

### Agent Capabilities
The fitness app project agent would handle:
- React Native component development
- FastAPI endpoint creation
- Database migrations
- Test writing and execution
- Claude API integration for AI features

---

## 6. Estimated Effort & Timeline

| Phase | Scope | Estimated Effort |
|-------|-------|-----------------|
| **Phase 1** - MVP | Auth, workouts, logging, basic progress | 4-6 weeks |
| **Phase 2** - Intelligence | AI plans, smart suggestions, NLP input | 3-4 weeks |
| **Phase 3** - Social | Friends, challenges, notifications | 3-4 weeks |
| **Phase 4** - Advanced | Health integrations, video, nutrition | 4-6 weeks |

**Total to full product**: ~14-20 weeks with DREAM Team AI agents accelerating development

---

## 7. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| App store approval delays | Launch delay | Follow Apple/Google guidelines from day 1 |
| Health data privacy (HIPAA-adjacent) | Legal/trust | Minimize PII, encrypt at rest, clear privacy policy |
| React Native performance for animations | UX quality | Use Reanimated library, native modules where needed |
| AI hallucination in workout advice | Safety | Add disclaimers, validate AI output, set guardrails |
| Offline sync conflicts | Data loss | Conflict resolution strategy, last-write-wins + merge |

---

## 8. Competitive Differentiation

What makes this fitness app stand out:

1. **AI-First Design** - Claude-powered personalized coaching that adapts in real-time
2. **Natural Language Interface** - Log workouts by just describing them
3. **Intelligent Programming** - Auto-generates periodized training plans
4. **Open Architecture** - Built on open-source stack, extensible via API
5. **DREAM Team Managed** - Rapid feature iteration via AI-powered development

---

## 9. Next Steps

1. **Create the repository** - Initialize `fitness-app` repo with React Native + Expo template
2. **Set up backend** - Bootstrap FastAPI backend with auth and basic models
3. **Add to DREAM Team** - Register as a managed project
4. **Build MVP** - Start with Phase 1 features (auth, workout library, logging)
5. **Integrate AI** - Connect Claude API for workout generation in Phase 2

---

## 10. Decision Needed

To proceed, we need alignment on:

- [ ] **Tech stack**: React Native (recommended) vs Flutter vs Native?
- [ ] **Backend hosting**: Self-hosted (matches DREAM Team) vs cloud (Supabase/Firebase)?
- [ ] **MVP scope**: Full Phase 1 or a slimmer proof-of-concept first?
- [ ] **Target platforms**: iOS-first, Android-first, or both simultaneously?
- [ ] **Repo structure**: Monorepo (frontend + backend) or separate repos?
