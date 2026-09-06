// Generated from canonical backend OpenAPI. Do not edit.
export interface paths {
    "/api/v1/analyses/{analysis_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Analysis Status */
        get: operations["analysis_status_api_v1_analyses__analysis_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/candidates/{candidate_id}/recommendations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Candidate Recommendations */
        get: operations["candidate_recommendations_api_v1_candidates__candidate_id__recommendations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/candidates/{candidate_id}/recommendations/{revision}/jobs/{job_id}/explanation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Explanation Status */
        get: operations["explanation_status_api_v1_candidates__candidate_id__recommendations__revision__jobs__job_id__explanation_get"];
        put?: never;
        /** Request Explanation */
        post: operations["request_explanation_api_v1_candidates__candidate_id__recommendations__revision__jobs__job_id__explanation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Job Detail */
        get: operations["job_detail_api_v1_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resumes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Resume */
        post: operations["upload_resume_api_v1_resumes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resumes/{resume_id}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Candidate Profile */
        get: operations["candidate_profile_api_v1_resumes__resume_id__profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/dev/fixtures": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Development Fixtures
         * @description Synthetic, public test data only. This is not a candidate-data endpoint.
         */
        get: operations["development_fixtures_dev_fixtures_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live */
        get: operations["live_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AnalysisRun */
        AnalysisRun: {
            /** Analysis Id */
            analysis_id: string;
            /** Candidate Id */
            candidate_id: string;
            /** Corpus Snapshot */
            corpus_snapshot: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error: components["schemas"]["ErrorDetail"] | null;
            /** Result Count */
            result_count: number;
            /** Resume Id */
            resume_id: string;
            /**
             * State
             * @enum {string}
             */
            state: "queued" | "extracting" | "profiling" | "matching" | "ready" | "failed";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Warnings */
            warnings: string[];
        };
        /** Body_upload_resume_api_v1_resumes_post */
        Body_upload_resume_api_v1_resumes_post: {
            /** File */
            file: string;
        };
        /** CandidateProfile */
        CandidateProfile: {
            /** Candidate Id */
            candidate_id: string;
            /** Education */
            education: components["schemas"]["Education"][];
            /** Estimated Experience Years */
            estimated_experience_years: number | null;
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Experience */
            experience: components["schemas"]["Experience"][];
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Extraction Warnings */
            extraction_warnings: string[];
            /** Job Titles */
            job_titles: string[];
            /** Language */
            language: string | null;
            /** Matching Enabled */
            matching_enabled: boolean;
            /** Organizations */
            organizations: string[];
            /** Profile Version */
            profile_version: number;
            /** Projects */
            projects: components["schemas"]["Project"][];
            /** Resume Id */
            resume_id: string;
            /** Skills */
            skills: components["schemas"]["SkillEvidence"][];
            /** Summary */
            summary: string | null;
        };
        /** Education */
        Education: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Institution */
            institution: string | null;
            /** Qualification */
            qualification: string | null;
        };
        /** EmbeddingRecord */
        EmbeddingRecord: {
            /** Dimensions */
            dimensions: number;
            /** Embedding Version */
            embedding_version: string;
            /** Entity Id */
            entity_id: string;
            /** Entity Version */
            entity_version: number;
            /** Model Id */
            model_id: string;
            /** Model Revision */
            model_revision: string;
            /** Preprocessing Version */
            preprocessing_version: string;
            /** Vector */
            vector: number[];
        };
        /** ErrorDetail */
        ErrorDetail: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Request Id */
            request_id: string;
            /** Retryable */
            retryable: boolean;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ErrorDetail"];
        };
        /** EvidenceRef */
        EvidenceRef: {
            /** Chunk Id */
            chunk_id: string;
            /** Document Id */
            document_id: string;
            /** Document Version */
            document_version: number;
            /** End */
            end: number;
            /** Excerpt */
            excerpt: string;
            /** Page */
            page?: number | null;
            /** Section */
            section?: string | null;
            /** Start */
            start: number;
        };
        /** Experience */
        Experience: {
            /** End Date */
            end_date?: string | null;
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Job Title */
            job_title: string | null;
            /** Organization */
            organization: string | null;
            /** Start Date */
            start_date?: string | null;
        };
        /** FixtureBundle */
        FixtureBundle: {
            analysis: components["schemas"]["AnalysisRun"];
            /** Description */
            description: string;
            /** Embeddings */
            embeddings: components["schemas"]["EmbeddingRecord"][];
            /** Errors */
            errors: components["schemas"]["ErrorResponse"][];
            /** Events */
            events: (components["schemas"]["ProfileReadyEvent"] | components["schemas"]["JobChangeEvent"] | components["schemas"]["ReconciliationEvent"])[];
            explanation: components["schemas"]["MatchExplanation"];
            /** Jobs */
            jobs: components["schemas"]["JobPosting"][];
            /** Match Runs */
            match_runs: components["schemas"]["MatchRun"][];
            /** Matches */
            matches: components["schemas"]["MatchResult"][];
            /**
             * Mode
             * @default fixture
             * @constant
             */
            mode: "fixture";
            /** Profiles */
            profiles: components["schemas"]["CandidateProfile"][];
            recommendations: components["schemas"]["RecommendationSet"];
        };
        /** JobChangeEvent */
        JobChangeEvent: {
            /** Content Ref */
            content_ref: string;
            /** Event Id */
            event_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            event_type: "job.created" | "job.expired" | "job.removed" | "job.updated";
            /** Job Id */
            job_id: string;
            /** Job Version */
            job_version: number;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
        };
        /** JobPosting */
        JobPosting: {
            /** Active */
            active: boolean;
            /** Company */
            company: string;
            /** Content Version */
            content_version: number;
            /**
             * Data Origin
             * @enum {string}
             */
            data_origin: "fixture" | "permitted_source";
            /** Description */
            description: string;
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Expires At */
            expires_at?: string | null;
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
            /** Job Id */
            job_id: string;
            /** Language */
            language: string | null;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /** Other Requirements */
            other_requirements: string[];
            /** Posted At */
            posted_at?: string | null;
            /** Requirements */
            requirements: components["schemas"]["JobRequirement"][];
            /** Source Id */
            source_id: string;
            /**
             * Source Url
             * Format: uri
             */
            source_url: string;
            /** Summary */
            summary: string | null;
            /** Title */
            title: string;
        };
        /** JobRequirement */
        JobRequirement: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Required */
            required: boolean;
            /** Skill */
            skill: string;
        };
        /** MatchExplanation */
        MatchExplanation: {
            /** Candidate Id */
            candidate_id: string;
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Gaps */
            gaps: string[];
            /** Generated At */
            generated_at: string | null;
            /** Job Id */
            job_id: string;
            /** Job Version */
            job_version: number;
            /** Model Version */
            model_version: string | null;
            /** Profile Version */
            profile_version: number;
            /** Prompt Version */
            prompt_version: string | null;
            /** Revision */
            revision: number;
            /** Scoring Version */
            scoring_version: string;
            /**
             * State
             * @enum {string}
             */
            state: "pending" | "ready" | "unavailable";
            /** Strengths */
            strengths: string[];
            /** Text */
            text: string | null;
        };
        /** MatchResult */
        MatchResult: {
            /** Candidate Id */
            candidate_id: string;
            /**
             * Data Origin
             * @enum {string}
             */
            data_origin: "fixture" | "computed";
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Gaps */
            gaps: string[];
            /** Job Id */
            job_id: string;
            /** Job Version */
            job_version: number;
            /**
             * Matched At
             * Format: date-time
             */
            matched_at: string;
            /** Profile Version */
            profile_version: number;
            /** Score */
            score: number;
            score_components: components["schemas"]["ScoreComponents"];
            /** Scoring Version */
            scoring_version: string;
            /** Short Reason */
            short_reason: string | null;
            /** Skill Comparison */
            skill_comparison: components["schemas"]["SkillComparison"][];
            /** Strengths */
            strengths: string[];
        };
        /** MatchRun */
        MatchRun: {
            /** Checkpoint */
            checkpoint: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error: components["schemas"]["ErrorDetail"] | null;
            /** Event */
            event: components["schemas"]["ProfileReadyEvent"] | components["schemas"]["JobChangeEvent"] | components["schemas"]["ReconciliationEvent"];
            /** Published Revisions */
            published_revisions: {
                [key: string]: number;
            };
            /** Run Id */
            run_id: string;
            /**
             * State
             * @enum {string}
             */
            state: "queued" | "running" | "ready" | "failed";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ProfileReadyEvent */
        ProfileReadyEvent: {
            /** Candidate Id */
            candidate_id: string;
            /** Event Id */
            event_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            event_type: "profile.ready";
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Profile Version */
            profile_version: number;
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
        };
        /** Project */
        Project: {
            /** Description */
            description: string;
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Name */
            name: string;
        };
        /** Recommendation */
        Recommendation: {
            /** Analysis Id */
            analysis_id?: string | null;
            /** Candidate Id */
            candidate_id: string;
            /**
             * Data Origin
             * @enum {string}
             */
            data_origin: "fixture" | "computed";
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Gaps */
            gaps: string[];
            /** Index Version */
            index_version: string;
            /** Job Id */
            job_id: string;
            /** Job Summary */
            job_summary: string | null;
            /** Job Version */
            job_version: number;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /** Match Run Id */
            match_run_id: string;
            /**
             * Matched At
             * Format: date-time
             */
            matched_at: string;
            /** Profile Version */
            profile_version: number;
            /** Rank */
            rank: number;
            /** Revision */
            revision: number;
            /** Score */
            score: number;
            score_components: components["schemas"]["ScoreComponents"];
            /** Scoring Version */
            scoring_version: string;
            /** Short Reason */
            short_reason: string | null;
            /** Skill Comparison */
            skill_comparison: components["schemas"]["SkillComparison"][];
            /**
             * Source Url
             * Format: uri
             */
            source_url: string;
            /** Strengths */
            strengths: string[];
        };
        /** RecommendationSet */
        RecommendationSet: {
            /** Candidate Id */
            candidate_id: string;
            /** Next Cursor */
            next_cursor?: string | null;
            /** Profile Version */
            profile_version: number;
            /**
             * Refresh State
             * @enum {string}
             */
            refresh_state: "idle" | "pending" | "failed";
            /** Results */
            results: components["schemas"]["Recommendation"][];
            /** Revision */
            revision: number;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ReconciliationEvent */
        ReconciliationEvent: {
            /** Candidate After Id */
            candidate_after_id?: string | null;
            /** Event Id */
            event_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            event_type: "reconciliation.requested";
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
        };
        /** ScoreComponents */
        ScoreComponents: {
            /** Model Revision */
            model_revision: string;
            /** Preprocessing Version */
            preprocessing_version: string;
            /**
             * Score Basis
             * @enum {string}
             */
            score_basis: "semantic_skills" | "semantic_only";
            /** Semantic Fit */
            semantic_fit: number;
            /** Semantic Weight */
            semantic_weight: number;
            /** Skill Coverage */
            skill_coverage: number | null;
            /** Skills Weight */
            skills_weight: number;
        };
        /** SkillComparison */
        SkillComparison: {
            /** Job Evidence */
            job_evidence: components["schemas"]["EvidenceRef"][];
            /** Required */
            required: boolean;
            /** Resume Evidence */
            resume_evidence: components["schemas"]["EvidenceRef"][];
            /** Skill */
            skill: string;
            /**
             * State
             * @enum {string}
             */
            state: "present" | "partial" | "missing";
            /** Uncertainty Note */
            uncertainty_note?: string | null;
        };
        /** SkillEvidence */
        SkillEvidence: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceRef"][];
            /** Name */
            name: string;
        };
        /** UploadAccepted */
        UploadAccepted: {
            /** Analysis Id */
            analysis_id: string;
            /** Candidate Id */
            candidate_id: string;
            /** Resume Id */
            resume_id: string;
            /** Status Url */
            status_url: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    analysis_status_api_v1_analyses__analysis_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                analysis_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    candidate_recommendations_api_v1_candidates__candidate_id__recommendations_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                candidate_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecommendationSet"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    explanation_status_api_v1_candidates__candidate_id__recommendations__revision__jobs__job_id__explanation_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                candidate_id: string;
                revision: number;
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchExplanation"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    request_explanation_api_v1_candidates__candidate_id__recommendations__revision__jobs__job_id__explanation_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                candidate_id: string;
                revision: number;
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchExplanation"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    job_detail_api_v1_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobPosting"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    upload_resume_api_v1_resumes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_resume_api_v1_resumes_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadAccepted"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    candidate_profile_api_v1_resumes__resume_id__profile_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidateProfile"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Planned feature; not implemented. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    development_fixtures_dev_fixtures_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FixtureBundle"];
                };
            };
        };
    };
    live_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    ready_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
}
