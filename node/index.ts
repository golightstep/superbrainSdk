import koffi from 'koffi';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';
import { LayeredCompression } from './lcc';

export class SuperbrainFabricError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'SuperbrainFabricError';
    }
}

export enum CreatorType {
    UNKNOWN = 0,
    HUMAN = 1,
    AGENT = 2,
    REFLECTION = 3,
    MIRROR = 4
}

export interface Provenance {
    source_id: string;
    creator_type: CreatorType;
    provenance_chain?: Provenance[];
    timestamp: number;
}

export interface MemoryMetadata {
    pointer_id: string;
    snippet: string;
    tag: string;
    liveliness: number;
    provenance?: Provenance;
    protected: boolean;
}

// Locate shared library
const libName = os.platform() === 'darwin' ? 'libsuperbrain.dylib' : 'libsuperbrain.so';

// Try finding it correctly in the package or local structure
let libPath = path.join(__dirname, '..', '..', 'lib', libName);
if (!fs.existsSync(libPath)) {
    libPath = path.join(process.cwd(), libName);
}
if (!fs.existsSync(libPath)) {
    libPath = path.join(process.cwd(), '..', 'lib', libName);
}

if (!fs.existsSync(libPath)) {
    throw new SuperbrainFabricError(`Shared library ${libName} not found. Ensure it is built and in the correct path.`);
}

const lib = koffi.load(libPath);

// C Bindings
const SB_NewClient = lib.func('SB_NewClient', 'str', ['str']);
const SB_NewClientWithEncryption = lib.func('SB_NewClientWithEncryption', 'str', ['str', 'uint8_t*', 'int']);
const SB_Register = lib.func('SB_Register', 'str', ['str', 'str']);
const SB_Allocate = lib.func('SB_Allocate', 'str', ['str', 'uint64_t']);
const SB_Write = lib.func('SB_Write', 'str', ['str', 'str', 'uint64_t', 'uint8_t*', 'uint64_t']);
const SB_Read = lib.func('SB_Read', 'str', ['str', 'str', 'uint64_t', 'uint64_t', '_Out_ uint8_t**', '_Out_ uint64_t*']);
const SB_Free = lib.func('SB_Free', 'str', ['str', 'str']);
const SB_GetPointer = lib.func('SB_GetPointer', 'str', ['str', 'str']);

const SB_WriteCognitive = lib.func('SB_WriteCognitive', 'str', ['str', 'str', 'uint64_t', 'uint8_t*', 'uint64_t', 'float', 'str', 'str', 'str', 'str']);
const SB_ResolveConflict = lib.func('SB_ResolveConflict', 'str', ['str', 'str', 'uint8_t*', 'uint64_t', 'str', '_Out_ uint8_t**', '_Out_ uint64_t*']);

const SB_ListMemories = lib.func('SB_ListMemories', 'str', ['str', 'str', 'str', 'int32']);
const SB_UpdateMetadata = lib.func('SB_UpdateMetadata', 'str', ['str', 'str', 'str', 'float']);
const SB_DeleteWithReason = lib.func('SB_DeleteWithReason', 'str', ['str', 'str', 'str']);
const SB_ProtectMemory = lib.func('SB_ProtectMemory', 'str', ['str', 'str', 'bool']);
const SB_SearchMemories = lib.func('SB_SearchMemories', 'str', ['str', 'str', 'int32']);
const SB_AddEdge = lib.func('SB_AddEdge', 'str', ['str', 'str', 'str', 'str', 'float']);
const SB_QueryGraph = lib.func('SB_QueryGraph', 'str', ['str', 'str', 'int32', 'str']);
const SB_NotifyRecall = lib.func('SB_NotifyRecall', 'str', ['str', 'str', 'str', 'str']);
const SB_GetMemoryHistory = lib.func('SB_GetMemoryHistory', 'str', ['str', 'str']);

export class Client {
    private clientId: string;
    private contextCache: string[] = [];
    private maxCacheSize = 50;

    constructor(addrs: string, encryptionKey?: Buffer) {
        let res: string;
        if (encryptionKey) {
            if (encryptionKey.length !== 32) {
                throw new SuperbrainFabricError('Encryption key must be exactly 32 bytes for AES-GCM-256');
            }
            res = SB_NewClientWithEncryption(addrs, encryptionKey, encryptionKey.length);
        } else {
            res = SB_NewClient(addrs);
        }

        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }

        this.clientId = res;
    }

    public register(agentId: string): void {
        const res = SB_Register(this.clientId, agentId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public allocate(size: number): string {
        const res = SB_Allocate(this.clientId, size);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
        return res;
    }

    /**
     * [V5.1 HERO API] 🧠
     * Write a memory to the Fabric with automated Layered Cognitive Compression (LCC).
     */
    public async writeMemory(content: string, options: { liveliness?: number, tag?: string, lccLevel?: number, mirrorReinforcement?: boolean } = {}): Promise<string | null> {
        const { liveliness = 0.5, tag = 'general', lccLevel = 1, mirrorReinforcement = false } = options;

        const compressed = LayeredCompression.compress(content, lccLevel, this.contextCache);
        if (compressed === null) return null;

        this.contextCache.unshift(content);
        if (this.contextCache.length > this.maxCacheSize) {
            this.contextCache.pop();
        }

        const data = Buffer.from(compressed);
        const ptrId = this.allocate(data.length);
        
        const provenance = { 
            creator_type: mirrorReinforcement ? CreatorType.MIRROR : CreatorType.AGENT,
            source_id: 'fabric-node-sdk'
        };

        this.writeCognitive(ptrId, 0, data, liveliness, 'write_memory', compressed.substring(0, 100), tag, provenance);
        return ptrId;
    }

    /**
     * [V5.1 HERO API] ✨
     * Active Memory Write: Enrich raw data with the Thalamus metadata layer.
     * Supports full Provenance Chains and History Versioning.
     */
    public writeCognitive(ptrId: string, offset: number, data: Buffer, liveliness: number, intent: string, summary: string, tag: string, provenance?: any): void {
        const provJSON = provenance ? JSON.stringify(provenance) : null;
        const res = SB_WriteCognitive(this.clientId, ptrId, offset, data, data.length, liveliness, intent, summary, tag, provJSON);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public read(ptrId: string, offset: number, length: number): Buffer {
        const outDataPtr = [null];
        const outLenPtr = [0];
        const res = SB_Read(this.clientId, ptrId, offset, length, outDataPtr, outLenPtr);

        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }

        const outBufPtr = outDataPtr[0] as any;
        const outLen = outLenPtr[0] as number;

        if (!outBufPtr || outLen === 0) {
            return Buffer.alloc(0);
        }

        const decodedBuffer = koffi.decode(outBufPtr, 'uint8_t', outLen);
        return Buffer.from(decodedBuffer);
    }

    public resolveConflict(ptrId: string, newData: Buffer, intent: string): Buffer {
        const outDataPtr = [null];
        const outLenPtr = [0];
        const res = SB_ResolveConflict(this.clientId, ptrId, newData, newData.length, intent, outDataPtr, outLenPtr);

        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }

        const outBufPtr = outDataPtr[0] as any;
        const outLen = outLenPtr[0] as number;

        if (!outBufPtr || outLen === 0) {
            return Buffer.alloc(0);
        }

        const decodedBuffer = koffi.decode(outBufPtr, 'uint8_t', outLen);
        return Buffer.from(decodedBuffer);
    }

    public free(ptrId: string): void {
        const res = SB_Free(this.clientId, ptrId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public attach(ptrId: string): void {
        const res = SB_GetPointer(this.clientId, ptrId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public listMemories(agentId: string = "", tag: string = "", creator: CreatorType = CreatorType.UNKNOWN): MemoryMetadata[] {
        const res = SB_ListMemories(this.clientId, agentId, tag, creator);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
        return res ? JSON.parse(res) : [];
    }

    public updateMetadata(ptrId: string, newTag: string, newLiveliness: number): void {
        const res = SB_UpdateMetadata(this.clientId, ptrId, newTag, newLiveliness);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public deleteWithReason(ptrId: string, reason: string): void {
        const res = SB_DeleteWithReason(this.clientId, ptrId, reason);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public protect(ptrId: string, protect: boolean): void {
        const res = SB_ProtectMemory(this.clientId, ptrId, protect);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public searchMemories(query: string, topK: number = 5): MemoryMetadata[] {
        const res = SB_SearchMemories(this.clientId, query, topK);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
        return res ? JSON.parse(res) : [];
    }

    public addEdge(sourceId: string, targetId: string, relation: string, weight: number = 1.0): void {
        const res = SB_AddEdge(this.clientId, sourceId, targetId, relation, weight);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public queryGraph(rootId: string, depth: number = 1, relationFilter: string = ""): { edges: any[], nodes: MemoryMetadata[] } {
        const res = SB_QueryGraph(this.clientId, rootId, depth, relationFilter);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
        return res ? JSON.parse(res) : { edges: [], nodes: [] };
    }

    public notifyRecall(pointerId: string, recalledBy: string, purpose: string): void {
        const res = SB_NotifyRecall(this.clientId, pointerId, recalledBy, purpose);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
    }

    public getMemoryHistory(pointerId: string): any[] {
        const res = SB_GetMemoryHistory(this.clientId, pointerId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainFabricError(res);
        }
        return res ? JSON.parse(res) : [];
    }
}
